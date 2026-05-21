"""
src/ibkr_streamer.py - High-Frequency Tick Ingestion (10ms / 100Hz)
Bypasses standard polling to ingest every single trade/quote tick directly
into QuestDB via the InfluxDB Line Protocol (ILP).
"""

import asyncio
import logging
import sys
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from datetime import time as dt_time
from typing import TYPE_CHECKING, Any, Optional
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from intelligence_bus import SharedIntelligenceBus


def _ensure_asyncio_loop() -> None:
    """Ensure a current asyncio event loop exists for this thread."""
    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        except Exception:
            pass

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    else:
        asyncio.set_event_loop(loop)


# Defer importing `ib_insync` until runtime to avoid creating an event loop
# at module import time in testing/static-analysis environments.

from tick_batcher import TICK_BATCHER

logger = logging.getLogger(__name__)


def _is_us_equity_market_open() -> bool:
    """Return True during regular US equity market hours."""
    try:
        now_et = datetime.now(ZoneInfo("America/New_York"))
        if now_et.weekday() >= 5:
            return False
        return dt_time(9, 30) <= now_et.time() <= dt_time(16, 0)
    except Exception:
        return True


class SpreadTracker:
    """
    Real-time bid/ask spread tracker per symbol.
    Uses an EMA over recent spread samples to smooth outliers.

    Usage:
        tracker = SpreadTracker()
        tracker.update("SPY", bid=415.10, ask=415.12)
        if tracker.is_wide("SPY"):   # skip trade — illiquid
            ...
    """

    def __init__(self, ema_period: int = 20, wide_threshold_bps: float = 20.0):
        """
        Parameters
        ----------
        ema_period          : Number of ticks to smooth spread over
        wide_threshold_bps  : Spread in basis points above which market is considered illiquid
        """
        self._ema_period = ema_period
        self._alpha = 2.0 / (ema_period + 1)
        self._threshold_bps = wide_threshold_bps
        self._spreads_bps: dict[str, float] = {}  # EMA spread per symbol
        self._raw_buf: dict[str, deque] = defaultdict(lambda: deque(maxlen=ema_period))

    def update(self, symbol: str, bid: float, ask: float) -> float | None:
        """Push a new bid/ask tick. Returns current EMA spread in bps, or None if invalid."""
        if bid <= 0 or ask <= 0 or bid >= ask:
            return None
        spread_bps = ((ask - bid) / bid) * 10_000
        self._raw_buf[symbol].append(spread_bps)

        if symbol in self._spreads_bps:
            self._spreads_bps[symbol] = (
                self._alpha * spread_bps + (1.0 - self._alpha) * self._spreads_bps[symbol]
            )
        else:
            # Seed with simple average until warmed up
            buf = self._raw_buf[symbol]
            self._spreads_bps[symbol] = sum(buf) / len(buf)
        return self._spreads_bps[symbol]

    def current_bps(self, symbol: str) -> float:
        """Return current EMA spread in basis points (default 10 bps if unknown)."""
        return self._spreads_bps.get(symbol, 10.0)

    def is_wide(self, symbol: str, threshold_bps: float | None = None) -> bool:
        """
        Returns True if the spread is abnormally wide.
        Callers should skip new entries when this is True.
        """
        threshold = threshold_bps if threshold_bps is not None else self._threshold_bps
        spread = self.current_bps(symbol)
        if spread > threshold:
            logger.debug(
                f"SpreadTracker: {symbol} spread {spread:.1f}bps > threshold {threshold:.1f}bps — WIDE"
            )
            return True
        return False

    def summary(self) -> dict[str, float]:
        """Returns current EMA spread bps for all tracked symbols."""
        return dict(self._spreads_bps)


# Module-level singleton
SPREAD_TRACKER = SpreadTracker()


class IBKRStreamer:
    """
    Real-time high-speed data streamer using IBKR's reqTickByTickData.
    Target: 0.01s (10ms) latency between market change and database ingestion.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 4002,
        client_id: int = 99,
        qdb_host: str = "localhost",
        qdb_ilp_port: int = 9009,
        bus: Optional["SharedIntelligenceBus"] = None,
        qdb_adapter: Optional[Any] = None,
    ) -> None:
        # IB instance is created lazily during `connect()` to avoid import-time
        # side-effects (some ib_insync dependencies create an event loop on import).
        self.ib = None
        self.host = host
        self.port = port
        self.client_id = client_id
        self.qdb_host = qdb_host
        self.qdb_ilp_port = qdb_ilp_port
        self.bus = bus
        self.qdb_adapter = qdb_adapter
        self.is_running = False
        self._loop_count = 0
        self.dropped_ticks = 0
        self._tick_cache: dict[str, dict] = {}  # live bid/ask/last per symbol
        self.spread_tracker = SPREAD_TRACKER  # shared singleton

        # Persistent Async Stream for QuestDB ILP
        self._qdb_writer: asyncio.StreamWriter | None = None
        self._qdb_lock = asyncio.Lock()

        self._bus_queue: asyncio.Queue = asyncio.Queue(maxsize=5000)
        self._publisher_task: asyncio.Task | None = None
        self._last_tick_time = datetime.now(timezone.utc)
        self._last_status_log: dict[tuple[int, str], float] = {}

    async def connect(self) -> None:
        """Connect to IBKR TWS/Gateway and QuestDB ILP."""
        # Lazily import and create IB instance here to avoid import-time event loop issues
        if self.ib is None:
            try:
                _ensure_asyncio_loop()
                from ib_insync import IB

                self.ib = IB()
            except Exception as e:
                logger.error(f"IBKRStreamer: ib_insync import/create failed: {e}")
                self.ib = None
                return
        # 1. Connect to QuestDB (Persistent ILP Session)
        from config import QUESTDB_ENABLED

        if QUESTDB_ENABLED:
            try:
                _reader, writer = await asyncio.open_connection(self.qdb_host, self.qdb_ilp_port)
                self._qdb_writer = writer
                logger.info(
                    f"IBKRStreamer: Connected to QuestDB ILP at {self.qdb_host}:{self.qdb_ilp_port}"
                )
            except (ConnectionRefusedError, OSError):
                logger.info(
                    f"IBKRStreamer: QuestDB Service not detected at {self.qdb_host}. Ticks will log to console/bus only."
                )
            except Exception as e:
                logger.warning(
                    f"IBKRStreamer: QuestDB ILP connection failed: {e}. Ticks will log to console only."
                )
        else:
            logger.info("IBKRStreamer: QuestDB ingestion DISABLED in config.")

        max_attempts = 5
        for attempt in range(max_attempts):
            for host in ["localhost", "127.0.0.1", "::1"]:
                try:
                    await self.ib.connectAsync(host, self.port, clientId=self.client_id)

                    # Deduplicated event registration
                    self.ib.errorEvent.clear()
                    self.ib.disconnectedEvent.clear()
                    self.ib.errorEvent += self._on_error
                    self.ib.disconnectedEvent += self._on_disconnect

                    self.ib.reqMarketDataType(3)

                    logger.info(
                        f"IBKRStreamer: Connected to TWS at {host}:{self.port} (Delayed Data Active)"
                    )
                    return
                except Exception as e:
                    logger.debug(
                        f"IBKRStreamer: Attempt {attempt + 1}/{max_attempts} failed for {host}:{self.port}: {e}"
                    )
                    if self.ib is not None:
                        try:
                            self.ib.disconnect()
                        except Exception:
                            pass

            wait_time = min(2**attempt, 30)  # Exponential backoff
            logger.warning(
                f"IBKRStreamer: Connection attempt {attempt + 1}/{max_attempts} failed for {self.host}:{self.port}. Retrying in {wait_time}s..."
            )
            await asyncio.sleep(wait_time)

        logger.error(
            "IBKRStreamer: All connection attempts failed. Ticks will be missing for this session."
        )

    async def _qdb_drain_worker(self) -> None:
        """Background worker to periodically drain the QuestDB buffer."""
        while self.is_running:
            try:
                if self._qdb_writer and not self._qdb_writer.is_closing():
                    async with self._qdb_lock:
                        await self._qdb_writer.drain()
                await asyncio.sleep(0.05)  # Drain 20 times a second
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5.0)

    async def _bus_publisher(self) -> None:
        """
        Sovereign Publisher: Single worker task to process tikcs.
        Ensures the system memory footprint stays CONSTANT despite 100Hz tick volume.
        """
        logger.info("IBKRStreamer: Sovereign Publisher worker started.")
        while self.is_running:
            try:
                # Wait for data or timeout to check is_running
                data = await self._bus_queue.get()
                if self.bus:
                    await self.bus.publish("tick.hft", data)
                self._bus_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"IBKRStreamer: Publisher error: {e}")
                await asyncio.sleep(0.1)

    def on_tick(self, tickers) -> None:
        """Callback for set of tickers identified by IBKR."""
        self._last_tick_time = datetime.now(timezone.utc)

        for ticker in tickers:
            symbol = ticker.contract.symbol

            bid = float(ticker.bid) if ticker.bid > 0 else 0.0
            ask = float(ticker.ask) if ticker.ask > 0 else 0.0
            last_p = float(ticker.last) if ticker.last > 0 else 0.0

            # Reject ticks that are older than 500ms to prevent trading on 'Cold' price data.
            if ticker.time:
                ticker_age = (
                    datetime.now(timezone.utc) - ticker.time.replace(tzinfo=timezone.utc)
                ).total_seconds()
                if ticker_age > 0.5:
                    logger.debug(f"IBKR: {symbol} tick stale ({ticker_age:.2f}s). Skipping.")
                    continue

            # Update tick cache and spread tracker
            self._tick_cache[symbol] = {"bid": bid, "ask": ask, "last": last_p}
            if bid > 0 and ask > 0:
                self.spread_tracker.update(symbol, bid, ask)

            # 1. Spread Check: Reject hallucinations in low liquidity
            if bid > 0 and ask > 0:
                if bid > ask:
                    logger.warning(
                        f" HALLUCINATION VETO: {symbol} Bid (${bid}) > Ask (${ask}). Broken broker state. Skipping."
                    )
                    continue

                spread_pct = (ask - bid) / bid
                if spread_pct > 0.05:
                    logger.warning(
                        f" LIQUIDITY VETO: {symbol} spread too wide ({spread_pct:.1%}). Hallucination rejected."
                    )
                    continue

            # 2. Price Discovery: Favor 'last', then 'bid/ask mean' if spread is tight
            target_price = last_p
            if target_price <= 0:
                if bid > 0 and ask > 0:
                    target_price = (bid + ask) / 2.0
                else:
                    # Final fallback to marketPrice() only if it's not None
                    target_price = float(ticker.marketPrice()) if ticker.marketPrice() > 0 else 0.0

            if target_price <= 0:
                continue

            last_size = (
                ticker.lastSize if (ticker.lastSize and ticker.lastSize > 0) else ticker.bidSize
            )

            # Push to TickBatcher — batched at 10Hz, prevents Bayesian/Dhatu firing 100x/s
            TICK_BATCHER.push(symbol, target_price, bid, ask, float(last_size or 0))

            # Tags must be escaped: spaces, commas, and equals signs.
            safe_symbol = str(symbol).replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")

            if self.qdb_adapter and self.qdb_adapter.enabled:
                self.qdb_adapter.log_tick(symbol, target_price, last_size or 0)
            elif self._qdb_writer and not self._qdb_writer.is_closing():
                try:
                    # Non-blocking write to QuestDB
                    now_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
                    line = f"ticks,symbol={safe_symbol} price={target_price},size={last_size or 0} {now_ns}\n"
                    self._qdb_writer.write(line.encode())
                except Exception as _qdb_err:
                    logger.debug(f"IBKRStreamer: QuestDB write skipped: {_qdb_err}")

            if self.bus is not None:
                try:
                    self._bus_queue.put_nowait(
                        {
                            "symbol": symbol,
                            "price": target_price,
                            "bid": bid if bid > 0 else target_price,
                            "ask": ask if ask > 0 else target_price,
                            "size": last_size,
                            "ts": time.time_ns(),
                        }
                    )
                except asyncio.QueueFull:
                    self.dropped_ticks += 1
                    if self.dropped_ticks % 100 == 0:
                        logger.warning(
                            f"IBKRStreamer: SILENT TICK DROP! (Total: {self.dropped_ticks}) - Bus Saturation."
                        )
                        if self.dropped_ticks >= 500 and self.bus:
                            self.bus.publish_sync(
                                "system.alert",
                                {
                                    "type": "LATENCY_CRITICAL",
                                    "source": "IBKRStreamer",
                                    "dropped_ticks": self.dropped_ticks,
                                    "message": "Critical Tick Drop detected. Market visibility may be compromised.",
                                },
                            )
                    pass
            logger.debug(f"TICK [{symbol}]: {target_price} (B: {bid}, A: {ask}) @ {last_size}")

    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract: Any) -> None:
        # 2104: Farm connection OK
        # 10167/10168/10089: Informational warnings about delayed data/subscriptions
        # 1100/1101/1102: Connection lost/restored (expected off-hours behavior)
        if errorCode in (2104, 2106, 2158, 2157, 10167, 10168, 10089, 1100, 1101, 1102):
            status_key = (errorCode, errorString)
            now = time.monotonic()
            last_log = self._last_status_log.get(status_key, 0.0)
            if now - last_log > 300.0:
                logger.info(f"IBKRStreamer [STATUS]: {errorCode} - {errorString}")
                self._last_status_log[status_key] = now
            else:
                logger.debug(f"IBKRStreamer [STATUS]: {errorCode} - {errorString}")
            return

        if errorCode >= 2100 and errorCode <= 2110:
            logger.debug(f"IBKRStreamer [INFO]: {errorCode} - {errorString}")
            return

        logger.error(f"IBKRStreamer [CRITICAL ERROR]: {reqId} {errorCode} {errorString}")

    def _on_disconnect(self) -> None:
        """Handle unexpected socket severance and trigger reconnect logic."""
        logger.warning("IBKRStreamer: Matrix Connection Severed. Waiting for recovery loop...")

    async def run(self, symbols: list[str]) -> None:
        """Starts streaming tick-by-tick data for the requested symbols."""
        self.is_running = True

        while self.is_running:
            try:
                if not self.ib or not self.ib.isConnected():
                    logger.info("IBKRStreamer: Connection required. Starting handshake...")
                    if self._qdb_writer:
                        self._qdb_writer.close()
                        self._qdb_writer = None
                    await self.connect()

                    if not self.ib or not self.ib.isConnected():
                        logger.warning("IBKRStreamer: Handshake failed. Retrying in 10s...")
                        await asyncio.sleep(10)
                        continue

                # Start background workers (Cleanup previous if exist)
                if (
                    hasattr(self, "_publisher_task")
                    and self._publisher_task
                    and not self._publisher_task.done()
                ):
                    self._publisher_task.cancel()
                if (
                    hasattr(self, "_drain_task")
                    and self._drain_task
                    and not self._drain_task.done()
                ):
                    self._drain_task.cancel()

                self._publisher_task = asyncio.create_task(self._bus_publisher())
                self._drain_task = asyncio.create_task(self._qdb_drain_worker())
                self._batcher_task = asyncio.create_task(TICK_BATCHER.run(self.bus))

                # 1. Bind events with Deduplication Guard
                try:
                    self.ib.pendingTickersEvent.disconnect(self.on_tick)
                except Exception:
                    pass  # Expected if not previously connected
                self.ib.pendingTickersEvent.connect(self.on_tick)
                self._last_tick_time = datetime.now(timezone.utc)
                logger.info("IBKRStreamer: Event listeners active.")

                from ib_insync import Stock

                contracts = [Stock(symbol=s, exchange="SMART", currency="USD") for s in symbols]

                # 2. Subscribe to all symbols
                current_tickers = {t.contract.symbol for t in self.ib.tickers()}
                for contract in contracts:
                    if contract.symbol not in current_tickers:
                        try:
                            self.ib.reqMktData(contract, "233", False, False)
                            logger.info(f"IBKRStreamer: Subscribed to {contract.symbol}")
                        except Exception as e:
                            logger.error(
                                f"IBKRStreamer: Subscription error for {contract.symbol}: {e}"
                            )

                # 3. Keep-alive loop with Reconnect Watchdog
                logger.info("IBKRStreamer: Matrix Pulse Monitoring active.")
                while self.is_running and self.ib.isConnected():
                    await asyncio.sleep(1.0)
                    self._loop_count += 1

                    # If market is open and we haven't seen a tick in 180s, something is wrong.
                    seconds_since_tick = (
                        datetime.now(timezone.utc) - self._last_tick_time
                    ).total_seconds()
                    if (
                        seconds_since_tick > 180
                        and self.is_running
                        and _is_us_equity_market_open()
                    ):
                        logger.warning(
                            f"IBKRStreamer: SILENT DATA GAP detected ({seconds_since_tick:.0f}s). Re-initializing..."
                        )
                        break

                if not self.ib.isConnected():
                    logger.warning("IBKRStreamer: Connection lost — entering recovery.")

            except asyncio.CancelledError:
                logger.info("IBKRStreamer: Cancellation received.")
                raise
            except Exception as e:
                logger.error(f"IBKRStreamer: Runtime error in main loop: {e}")
                await asyncio.sleep(5)
            finally:
                if hasattr(self, "_publisher_task") and self._publisher_task:
                    self._publisher_task.cancel()
                if hasattr(self, "_drain_task") and self._drain_task:
                    self._drain_task.cancel()
                if hasattr(self, "_batcher_task") and self._batcher_task:
                    self._batcher_task.cancel()
                try:
                    if self.ib:
                        self.ib.pendingTickersEvent.disconnect(self.on_tick)
                except Exception:
                    pass  # Expected if not connected
                if self.ib and self.ib.isConnected():
                    logger.info("IBKRStreamer: Cleaning up IBKR connection...")
                    try:
                        await asyncio.to_thread(self.ib.disconnect)
                    except Exception as _disc_err:
                        logger.debug(f"IBKRStreamer: Non-critical disconnect error: {_disc_err}")

    async def stop(self) -> None:
        """Stop the streamer."""
        self.is_running = False
        if hasattr(self, "_publisher_task") and self._publisher_task:
            self._publisher_task.cancel()
            try:
                await self._publisher_task
            except asyncio.CancelledError:
                pass
        if self.ib is not None:
            try:
                await asyncio.to_thread(self.ib.disconnect)
            except Exception as e:
                logger.debug(f"IBKRStreamer: Stop disconnect error: {e}")
        logger.info("IBKRStreamer: Disconnected and stopped.")
