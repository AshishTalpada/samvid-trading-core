"""
TradingView quote streamer.

Provides a free real-time quote lane through TradingView's websocket protocol.
IBKR can then remain focused on broker state and order execution while this
streamer feeds the internal tick bus.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import websockets

from market_calendar import is_us_equity_market_open
from tick_batcher import TICK_BATCHER

if TYPE_CHECKING:
    from intelligence_bus import SharedIntelligenceBus
    from questdb_adapter import QuestDBAdapter

logger = logging.getLogger(__name__)


DEFAULT_TV_EXCHANGES: dict[str, str] = {
    "SPY": "AMEX",
    "QQQ": "NASDAQ",
    "IWM": "AMEX",
    "DIA": "AMEX",
    "XLK": "AMEX",
    "XLF": "AMEX",
    "NVDA": "NASDAQ",
    "TSLA": "NASDAQ",
    "META": "NASDAQ",
    "AAPL": "NASDAQ",
    "MSFT": "NASDAQ",
    "GOOGL": "NASDAQ",
    "AMZN": "NASDAQ",
    "AVGO": "NASDAQ",
}


@dataclass(slots=True)
class TVQuote:
    symbol: str
    price: float
    bid: float
    ask: float
    size: float
    change: float
    change_pct: float
    market_status: str
    exchange_symbol: str
    ts_ns: int

    def to_tick_payload(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "price": self.price,
            "bid": self.bid or self.price,
            "ask": self.ask or self.price,
            "size": self.size,
            "change": self.change,
            "change_pct": self.change_pct,
            "market_status": self.market_status,
            "source": "TradingView_WS",
            "exchange_symbol": self.exchange_symbol,
            "ts": self.ts_ns,
        }


class TVQuoteStreamer:
    """
    TradingView quote websocket client.

    Publishes:
    - tick.hft: every valid quote update
    - tick.batch: indirectly through the existing TickBatcher
    - candle.batch: throttled scanner wake pulse when symbols receive updates
    """

    def __init__(
        self,
        bus: "SharedIntelligenceBus | None" = None,
        qdb_adapter: "QuestDBAdapter | None" = None,
        url: str = "wss://data.tradingview.com/socket.io/websocket",
    ) -> None:
        self.url = url
        self.bus = bus
        self.qdb_adapter = qdb_adapter
        self.session_id = f"qs_{os.urandom(6).hex()}"
        self.is_running = False
        self._ws = None
        self._connected = False
        self._last_quote_at = 0.0
        self._last_status_log = 0.0
        self._last_candle_pulse = 0.0
        self._pending_pulse_symbols: set[str] = set()
        self._short_disconnects = 0
        self._instability_cycles = 0
        self._last_after_hours_pause_log = 0.0
        self._allow_after_hours = os.getenv("SOVEREIGN_TV_QUOTES_AFTER_HOURS", "0") == "1"
        self._after_hours_pause_sec = max(
            60, int(os.getenv("SOVEREIGN_TV_QUOTES_AFTER_HOURS_PAUSE_SEC", "300"))
        )
        self._candle_pulse_sec = max(
            0.25, float(os.getenv("SOVEREIGN_TV_QUOTES_CANDLE_PULSE_SEC", "1.0"))
        )
        self.dropped_ticks = 0
        self.quotes_seen = 0
        self._symbol_by_tv: dict[str, str] = {}
        self._last_payload_by_symbol: dict[str, dict[str, Any]] = {}

    @property
    def connected(self) -> bool:
        return self._connected

    @staticmethod
    def _is_us_equity_market_open() -> bool:
        return is_us_equity_market_open()

    @staticmethod
    def _format_message(data: dict[str, Any]) -> str:
        msg = json.dumps(data, separators=(",", ":"))
        return f"~m~{len(msg)}~m~{msg}"

    @staticmethod
    def parse_messages(raw_data: str) -> list[dict[str, Any]]:
        """Decode TradingView ~m~length~m~JSON websocket frames."""
        results: list[dict[str, Any]] = []
        ptr = 0
        while ptr < len(raw_data):
            if raw_data.startswith("~h~", ptr):
                break
            if not raw_data.startswith("~m~", ptr):
                break
            end_len_idx = raw_data.find("~m~", ptr + 3)
            if end_len_idx == -1:
                break
            try:
                msg_len = int(raw_data[ptr + 3 : end_len_idx])
            except ValueError:
                break
            start_json = end_len_idx + 3
            end_json = start_json + msg_len
            if end_json > len(raw_data):
                break
            try:
                results.append(json.loads(raw_data[start_json:end_json]))
            except json.JSONDecodeError:
                pass
            ptr = end_json
        return results

    def _tv_symbol(self, symbol: str) -> str:
        raw = symbol.strip().upper()
        if ":" in raw:
            return raw
        exchange = DEFAULT_TV_EXCHANGES.get(raw, "NASDAQ")
        return f"{exchange}:{raw}"

    def _build_symbol_maps(self, symbols: list[str]) -> list[str]:
        tv_symbols: list[str] = []
        self._symbol_by_tv.clear()
        for raw in symbols:
            symbol = str(raw).strip().upper()
            if not symbol:
                continue
            tv_symbol = self._tv_symbol(symbol)
            tv_symbols.append(tv_symbol)
            self._symbol_by_tv[tv_symbol] = symbol.split(":", 1)[-1]
        return tv_symbols

    @staticmethod
    def _to_float(value: Any, default: float = 0.0) -> float:
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

    def _quote_from_message(self, msg: dict[str, Any]) -> TVQuote | None:
        if msg.get("m") != "qsd":
            return None
        params = msg.get("p", [])
        if len(params) < 2 or not isinstance(params[1], dict):
            return None
        quote_data = params[1]
        tv_symbol = str(quote_data.get("n") or "")
        values = quote_data.get("v")
        if not tv_symbol or not isinstance(values, dict):
            return None

        symbol = self._symbol_by_tv.get(tv_symbol, tv_symbol.split(":")[-1])
        price = self._to_float(
            values.get("lp", values.get("last_price", values.get("bid", values.get("ask"))))
        )
        bid = self._to_float(values.get("bid"))
        ask = self._to_float(values.get("ask"))
        if price <= 0 and bid > 0 and ask > 0:
            price = (bid + ask) / 2.0
        if price <= 0:
            return None
        if bid > 0 and ask > 0 and bid > ask:
            logger.debug("TVQuoteStreamer: rejected crossed quote for %s.", symbol)
            return None

        size = self._to_float(values.get("last_volume", values.get("volume")))
        return TVQuote(
            symbol=symbol,
            price=price,
            bid=bid,
            ask=ask,
            size=size,
            change=self._to_float(values.get("ch")),
            change_pct=self._to_float(values.get("chp")),
            market_status=str(values.get("market_status", "")),
            exchange_symbol=tv_symbol,
            ts_ns=time.time_ns(),
        )

    async def _send_setup(self, ws: Any, symbols: list[str]) -> None:
        await ws.send(self._format_message({"m": "quote_create_session", "p": [self.session_id]}))
        fields = [
            "lp",
            "last_price",
            "bid",
            "ask",
            "volume",
            "last_volume",
            "ch",
            "chp",
            "market_status",
            "rtc",
            "currency_code",
            "pricescale",
        ]
        await ws.send(self._format_message({"m": "quote_set_fields", "p": [self.session_id, *fields]}))
        for tv_symbol in symbols:
            await ws.send(
                self._format_message(
                    {"m": "quote_add_symbols", "p": [self.session_id, tv_symbol]}
                )
            )

    async def _publish_quote(self, quote: TVQuote) -> None:
        payload = quote.to_tick_payload()
        self._last_payload_by_symbol[quote.symbol] = payload
        self.quotes_seen += 1
        self._last_quote_at = time.monotonic()

        TICK_BATCHER.push(quote.symbol, quote.price, quote.bid, quote.ask, quote.size)

        if self.qdb_adapter and getattr(self.qdb_adapter, "enabled", False):
            try:
                self.qdb_adapter.log_tick(quote.symbol, quote.price, quote.size)
            except Exception as exc:
                logger.debug("TVQuoteStreamer: QuestDB tick write skipped: %s", exc)

        if self.bus is not None:
            try:
                await self.bus.publish("tick.hft", payload)
                self._pending_pulse_symbols.add(quote.symbol)
                await self._maybe_publish_candle_pulse()
            except Exception as exc:
                self.dropped_ticks += 1
                if self.dropped_ticks % 100 == 0:
                    logger.warning(
                        "TVQuoteStreamer: bus publish drops=%s (%s).",
                        self.dropped_ticks,
                        exc,
                    )

    async def _maybe_publish_candle_pulse(self) -> None:
        if not self.bus or not self._pending_pulse_symbols:
            return
        now = time.monotonic()
        if now - self._last_candle_pulse < self._candle_pulse_sec:
            return
        symbols = sorted(self._pending_pulse_symbols)
        self._pending_pulse_symbols.clear()
        self._last_candle_pulse = now
        await self.bus.publish(
            "candle.batch",
            {
                "source": "TradingView_WS",
                "symbols": symbols,
                "count": len(symbols),
                "timestamp": time.time_ns(),
            },
        )

    async def run(self, symbols: list[str]) -> None:
        self.is_running = True
        tv_symbols = self._build_symbol_maps(symbols)
        if not tv_symbols:
            logger.warning("TVQuoteStreamer: no symbols configured; streamer disabled.")
            return

        headers = {
            "Origin": "https://www.tradingview.com",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        logger.info(
            "TVQuoteStreamer: starting free quote lane for %s symbols.",
            len(tv_symbols),
        )

        while self.is_running:
            if not self._allow_after_hours and not self._is_us_equity_market_open():
                now_mono = time.monotonic()
                if now_mono - self._last_after_hours_pause_log > self._after_hours_pause_sec:
                    logger.info(
                        "TVQuoteStreamer: paused while US equity market is closed "
                        "(set SOVEREIGN_TV_QUOTES_AFTER_HOURS=1 to force it on)."
                    )
                    self._last_after_hours_pause_log = now_mono
                await asyncio.sleep(self._after_hours_pause_sec)
                continue

            connected_at = time.monotonic()
            try:
                async with websockets.connect(
                    self.url,
                    additional_headers=headers,
                    open_timeout=20.0,
                    ping_interval=15,
                    ping_timeout=10,
                ) as ws:
                    self._ws = ws
                    self._connected = True
                    await self._send_setup(ws, tv_symbols)
                    logger.info("TVQuoteStreamer: TradingView quote feed established.")

                    async for message in ws:
                        if not self.is_running:
                            break
                        if not isinstance(message, str):
                            continue
                        if message.startswith("~h~"):
                            await ws.send(message)
                            continue
                        for msg in self.parse_messages(message):
                            quote = self._quote_from_message(msg)
                            if quote is not None:
                                await self._publish_quote(quote)

                        now = time.monotonic()
                        if now - self._last_status_log > 300.0 and self.quotes_seen:
                            logger.info(
                                "TVQuoteStreamer: online quotes=%s drops=%s symbols=%s.",
                                self.quotes_seen,
                                self.dropped_ticks,
                                len(self._last_payload_by_symbol),
                            )
                            self._last_status_log = now

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning("TVQuoteStreamer: transient websocket failure: %s", exc)
            finally:
                self._connected = False
                session_age = time.monotonic() - connected_at
                if session_age < 5.0:
                    self._short_disconnects += 1
                elif session_age > 120.0:
                    self._short_disconnects = 0
                    self._instability_cycles = 0
                if self._short_disconnects >= 5:
                    self._instability_cycles += 1
                    cooldown = min(900, 60 * (2 ** min(self._instability_cycles - 1, 4)))
                    logger.warning(
                        "TVQuoteStreamer: unstable connection; cooling down for %ss.",
                        cooldown,
                    )
                    await asyncio.sleep(cooldown)
                    self._short_disconnects = 0

            await asyncio.sleep(5.0)

    async def stop(self) -> None:
        self.is_running = False
        ws = self._ws
        self._ws = None
        if ws is not None:
            try:
                await ws.close()
            except Exception:
                pass
        self._connected = False
        logger.info("TVQuoteStreamer: stopped.")
