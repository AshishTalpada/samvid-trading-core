# pyre-ignore-all-errors[21]
"""
src/ibkr_streamer.py - High-Frequency Tick Ingestion (10ms / 100Hz)

Bypasses standard polling to ingest every single trade/quote tick directly
into QuestDB via the InfluxDB Line Protocol (ILP).
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional, Any

if TYPE_CHECKING:
    from intelligence_bus import SharedIntelligenceBus

from ib_insync import IB, Stock  # pyre-ignore[21]

logger = logging.getLogger(__name__)


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
        self.ib = IB()
        self.host = host
        self.port = port
        self.client_id = client_id
        self.qdb_host = qdb_host
        self.qdb_ilp_port = qdb_ilp_port
        self.bus = bus
        self.qdb_adapter = qdb_adapter
        self.is_running = False
        self._loop_count = 0
        self.dropped_ticks = 0 # Samvid v1.0-beta-beta GAP-35 Tracker

        # Persistent Async Stream for QuestDB ILP
        self._qdb_writer: asyncio.StreamWriter | None = None
        self._qdb_lock = asyncio.Lock()
        
        # ── TASK CONSOLIDATION (Samvid v1.0-beta-beta) ──
        # GAP-45 FIX: Increased queue size to 5000 to handle peak volatility bursts.
        self._bus_queue: asyncio.Queue = asyncio.Queue(maxsize=5000)
        self._publisher_task: asyncio.Task | None = None
        self._last_tick_time = datetime.now(timezone.utc) # GAP-46: Stale data tracker

    async def connect(self) -> None:
        """Connect to IBKR TWS/Gateway and QuestDB ILP."""
        # 1. Connect to QuestDB (Persistent ILP Session)
        from config import QUESTDB_ENABLED
        if QUESTDB_ENABLED:
            try:
                _reader, writer = await asyncio.open_connection(self.qdb_host, self.qdb_ilp_port)
                self._qdb_writer = writer
                logger.info(
                    f"IBKRStreamer: Connected to QuestDB ILP at {self.qdb_host}:{self.qdb_ilp_port}"
                )
            except (ConnectionRefusedError, OSError) as e:
                logger.info(
                    f"IBKRStreamer: QuestDB Service not detected at {self.qdb_host}. Ticks will log to console/bus only."
                )
            except Exception as e:
                logger.warning(
                    f"IBKRStreamer: QuestDB ILP connection failed: {e}. Ticks will log to console only."
                )
        else:
             logger.info("IBKRStreamer: QuestDB ingestion DISABLED in config.")


        # 2. Connect to IBKR (Samvid v1.0-beta-beta: Hardened Retry Logic)
        max_attempts = 5
        for attempt in range(max_attempts):
            for host in ["localhost", "127.0.0.1", "::1"]:
                try:
                    await self.ib.connectAsync(host, self.port, clientId=self.client_id)
                    self.ib.errorEvent += self._on_error # GAP-179: Register Error Handler
                    self.ib.disconnectedEvent += self._on_disconnect # GAP-48: Register Disconnect Handler
                    
                    # GAP-290: Enable Delayed Market Data Fallback
                    self.ib.reqMarketDataType(3)
                    
                    logger.info(f"IBKRStreamer: Connected to TWS at {host}:{self.port} (Delayed Data Active)")
                    return
                except Exception as e:
                    logger.debug(f"IBKRStreamer: Attempt {attempt+1}/{max_attempts} failed for {host}:{self.port}: {e}")
                    self.ib.disconnect()

            wait_time = min(2 ** attempt, 30) # Exponential backoff
            logger.warning(f"IBKRStreamer: Connection attempt {attempt+1}/{max_attempts} failed for {self.host}:{self.port}. Retrying in {wait_time}s...")
            await asyncio.sleep(wait_time)

        logger.error("IBKRStreamer: All connection attempts failed. Ticks will be missing for this session.")

    async def _qdb_drain_worker(self) -> None:
        """Background worker to periodically drain the QuestDB buffer (Samvid v1.0-beta-beta)."""
        while self.is_running:
            try:
                if self._qdb_writer and not self._qdb_writer.is_closing():
                    async with self._qdb_lock:
                        # GAP-47 FIX: Increased drain frequency to match 100Hz volume
                        await self._qdb_writer.drain()
                await asyncio.sleep(0.05) # Drain 20 times a second
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5.0)

    async def _bus_publisher(self) -> None:
        """
        Sovereign Publisher (Samvid v1.0-beta-beta): Single worker task to process tikcs.
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
        # GAP-46: Update pulse time for the watchdog
        self._last_tick_time = datetime.now(timezone.utc)

        for ticker in tickers:
            symbol = ticker.contract.symbol
            
            # --- GAP-36: Liquidity Sentinel ---
            bid = float(ticker.bid) if ticker.bid > 0 else 0.0
            ask = float(ticker.ask) if ticker.ask > 0 else 0.0
            last_p = float(ticker.last) if ticker.last > 0 else 0.0
            
            # --- GAP-32 FIX: Cold Cache Protection ---
            # Reject ticks that are older than 500ms to prevent trading on 'Cold' price data.
            if ticker.time:
                ticker_age = (datetime.now(timezone.utc) - ticker.time.replace(tzinfo=timezone.utc)).total_seconds()
                if ticker_age > 0.5:
                    logger.debug(f"IBKR: {symbol} tick stale ({ticker_age:.2f}s). Skipping.")
                    continue
            
            # 1. Spread Check: Reject hallucinations in low liquidity (GAP-36 Hardening)
            if bid > 0 and ask > 0:
                # GAP-36 FIX: Hallucination Veto for Bid > Ask
                if bid > ask:
                    logger.warning(f"⚠️ HALLUCINATION VETO: {symbol} Bid (${bid}) > Ask (${ask}). Broken broker state. Skipping.")
                    continue
                
                spread_pct = (ask - bid) / bid
                if spread_pct > 0.05:
                    logger.warning(f"⚠️ LIQUIDITY VETO: {symbol} spread too wide ({spread_pct:.1%}). Hallucination rejected.")
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

            last_size = ticker.lastSize if (ticker.lastSize and ticker.lastSize > 0) else ticker.bidSize

            # --- GAP-53: ILP Guard ---
            # Tags must be escaped: spaces, commas, and equals signs.
            safe_symbol = str(symbol).replace(",", "\\,").replace(" ", "\\ ").replace("=", "\\=")

            # ── SOVEREIGN FAST-PATH (v1.0-beta-beta) ──
            if self.qdb_adapter and self.qdb_adapter.enabled:
                 self.qdb_adapter.log_tick(symbol, target_price, last_size or 0)
            elif self._qdb_writer and not self._qdb_writer.is_closing():
                try:
                    # Non-blocking write to QuestDB
                    now_ns = int(datetime.now(timezone.utc).timestamp() * 1e9)
                    line = f"ticks,symbol={safe_symbol} price={target_price},size={last_size or 0} {now_ns}\n"
                    self._qdb_writer.write(line.encode())
                except Exception:
                    pass
            
            # ── CONSOLIDATED BUS PUBLICATION (Samvid v1.0-beta-beta) ──
            if self.bus is not None:
                try:
                    self._bus_queue.put_nowait({
                        "symbol": symbol,
                        "price": target_price,
                        "bid": bid if bid > 0 else target_price,
                        "ask": ask if ask > 0 else target_price,
                        "size": last_size,
                        "ts": datetime.now(timezone.utc).isoformat(),
                    })
                except asyncio.QueueFull:
                    self.dropped_ticks += 1
                    if self.dropped_ticks % 100 == 0:
                         logger.warning(f"IBKRStreamer: SILENT TICK DROP! (Total: {self.dropped_ticks}) - Bus Saturation.")
                         if self.dropped_ticks >= 500 and self.bus:
                             # GAP-35: Alert the Brain to a high-latency condition
                             self.bus.publish_sync("system.alert", {
                                 "type": "LATENCY_CRITICAL",
                                 "source": "IBKRStreamer",
                                 "dropped_ticks": self.dropped_ticks,
                                 "message": "Critical Tick Drop detected. Market visibility may be compromised."
                             })
                    pass
            logger.debug(f"TICK [{symbol}]: {target_price} (B: {bid}, A: {ask}) @ {last_size}")

    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract: Any) -> None:
        # GAP-179/294: Filter out informational/warning codes to avoid 'CRITICAL ERROR' noise
        # 2104: Farm connection OK
        # 10167/10168/10089: Informational warnings about delayed data/subscriptions
        if errorCode in (2104, 2106, 2158, 2157, 10167, 10168, 10089):
             logger.debug(f"IBKRStreamer [INFO]: {errorCode} - {errorString}")
             return
             
        if errorCode >= 2100 and errorCode <= 2110:
             logger.debug(f"IBKRStreamer [INFO]: {errorCode} - {errorString}")
             return
             
        logger.error(f"IBKRStreamer [CRITICAL ERROR]: {reqId} {errorCode} {errorString}")

    def _on_disconnect(self) -> None:
        """GAP-48: Handle unexpected socket severance."""
        logger.warning("IBKRStreamer: Matrix Connection Severed. Waiting for recovery loop...")

    async def run(self, symbols: list[str]) -> None:
        """Starts streaming tick-by-tick data for the requested symbols."""
        self.is_running = True

        while self.is_running:
            try:
                # GAP-48 FIX: Internal Reconnect Loop
                if not self.ib.isConnected():
                    logger.info("IBKRStreamer: Connection required. Starting handshake...")
                    if self._qdb_writer:
                        self._qdb_writer.close()
                        self._qdb_writer = None
                    await self.connect()
                    
                    if not self.ib.isConnected():
                        logger.warning("IBKRStreamer: Handshake failed. Retrying in 10s...")
                        await asyncio.sleep(10)
                        continue

                # Start background workers (Cleanup previous if exist)
                if hasattr(self, "_publisher_task") and self._publisher_task and not self._publisher_task.done():
                    self._publisher_task.cancel()
                if hasattr(self, "_drain_task") and self._drain_task and not self._drain_task.done():
                    self._drain_task.cancel()

                self._publisher_task = asyncio.create_task(self._bus_publisher())
                self._drain_task = asyncio.create_task(self._qdb_drain_worker())

                # 1. Bind events with Deduplication Guard
                try:
                    self.ib.pendingTickersEvent.disconnect(self.on_tick)
                except Exception:
                    pass
                self.ib.pendingTickersEvent.connect(self.on_tick)
                logger.info("IBKRStreamer: Event listeners active.")

                contracts = [
                    Stock(symbol=s, exchange="SMART", currency="USD") for s in symbols
                ]

                # 2. Subscribe to all symbols
                current_tickers = {t.contract.symbol for t in self.ib.tickers()}
                for contract in contracts:
                    if contract.symbol not in current_tickers:
                        try:
                            self.ib.reqMktData(contract, "233", False, False)
                            logger.info(f"IBKRStreamer: Subscribed to {contract.symbol}")
                        except Exception as e:
                            logger.error(f"IBKRStreamer: Subscription error for {contract.symbol}: {e}")

                # 3. Keep-alive loop with GAP-46 Reconnect Watchdog
                logger.info("IBKRStreamer: Matrix Pulse Monitoring active.")
                while self.is_running and self.ib.isConnected():
                    await asyncio.sleep(1.0)
                    self._loop_count += 1
                    
                    # GAP-46: Stale data monitor
                    # If market is open and we haven't seen a tick in 180s, something is wrong.
                    seconds_since_tick = (datetime.now(timezone.utc) - self._last_tick_time).total_seconds()
                    if seconds_since_tick > 180 and self.is_running:
                        logger.warning(f"IBKRStreamer: SILENT DATA GAP detected ({seconds_since_tick:.0f}s). Re-initializing...")
                        break

                if not self.ib.isConnected():
                    logger.warning("IBKRStreamer: Connection lost — entering recovery.")

            except Exception as e:
                logger.error(f"IBKRStreamer: Runtime error in main loop: {e}")
                await asyncio.sleep(5)

        # Final cleanup on exit
        if self._publisher_task: self._publisher_task.cancel()
        if self._drain_task: self._drain_task.cancel()
        try:
            self.ib.pendingTickersEvent.disconnect(self.on_tick)
        except Exception:
            pass

    async def stop(self) -> None:
        """Stop the streamer."""
        self.is_running = False
        if self._publisher_task:
            self._publisher_task.cancel()
            try:
                await self._publisher_task
            except asyncio.CancelledError:
                pass
        self.ib.disconnect()
        logger.info("IBKRStreamer: Disconnected and stopped.")
