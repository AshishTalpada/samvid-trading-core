"""
src/questdb_candle_writer.py — Live OHLCV Candle Aggregator → QuestDB
Subscribes to tick.batch events and builds 1m/5m/15m candles in memory.
Writes completed bars to QuestDB via ILP, bypassing SQLite for live path.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from intelligence_bus import SharedIntelligenceBus
    from questdb_adapter import QuestDBAdapter

logger = logging.getLogger("CandleWriter")

_TF_SECONDS = {"1m": 60, "5m": 300, "15m": 900}


@dataclass
class Bar:
    symbol: str
    timeframe: str
    ts_open: float
    open: float = 0.0
    high: float = 0.0
    low: float = float("inf")
    close: float = 0.0
    volume: float = 0.0
    tick_count: int = 0

    def update(self, price: float, volume: float, ticks: int = 1) -> None:
        if self.tick_count == 0:
            self.open = price
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += volume
        self.tick_count += ticks

    def to_ilp(self) -> str:
        safe = self.symbol.replace(",", "\\,").replace(" ", "\\ ")
        ts_ns = int(self.ts_open * 1e9)
        low = self.low if self.low < float("inf") else self.close
        return (
            f"ohlcv_live,symbol={safe},tf={self.timeframe} "
            f"open={self.open},high={self.high},low={low},"
            f"close={self.close},volume={self.volume},ticks={self.tick_count}i "
            f"{ts_ns}\n"
        )


class CandleWriter:
    """
    Aggregates tick.batch events into OHLCV candles and writes them to QuestDB.
    Keeps a rolling in-memory window so brain.py can call get_bars()
    instead of executing a SQLite query on the hot path.
    """

    def __init__(
        self,
        qdb_adapter: "QuestDBAdapter | None" = None,
        timeframes: list[str] | None = None,
        memory_bars: int = 200,
    ):
        self._qdb = qdb_adapter
        self._timeframes = timeframes or ["1m", "5m", "15m"]
        self._memory = memory_bars
        self._active: dict[str, dict[str, Bar]] = defaultdict(dict)
        self._history: dict[str, dict[str, deque]] = defaultdict(
            lambda: {tf: deque(maxlen=self._memory) for tf in self._timeframes}
        )
        self._bars_written = 0

    # ── public reader ─────────────────────────────────────────────────────────

    def get_bars(self, symbol: str, timeframe: str = "5m", n: int = 100) -> list[Bar]:
        """Return last N completed bars. Replaces SQLite SELECT on the scanner path."""
        hist = self._history.get(symbol, {}).get(timeframe)
        return list(hist)[-n:] if hist else []

    def get_ohlcv(self, symbol: str, timeframe: str = "5m", n: int = 100) -> dict:
        bars = self.get_bars(symbol, timeframe, n)
        return {
            "open": [b.open for b in bars],
            "high": [b.high for b in bars],
            "low": [b.low for b in bars],
            "close": [b.close for b in bars],
            "volume": [b.volume for b in bars],
        }

    # ── bus wiring ────────────────────────────────────────────────────────────

    async def start(self, bus: "SharedIntelligenceBus") -> None:
        bus.subscribe("tick.batch", self._on_batch)
        logger.info(f"CandleWriter: Active | timeframes={self._timeframes}")

    async def _on_batch(self, data: dict) -> None:
        symbol = data.get("symbol")
        price = float(data.get("price", 0.0))
        volume = float(data.get("volume", 0.0))
        ticks = int(data.get("count", 1))

        if not symbol or price <= 0:
            return

        now = time.time()
        for tf in self._timeframes:
            tf_secs = _TF_SECONDS[tf]
            bar_ts = (now // tf_secs) * tf_secs
            active = self._active[symbol]

            # Close stale bar
            if tf in active and active[tf].ts_open < bar_ts:
                closed = active.pop(tf)
                self._history[symbol][tf].append(closed)
                await self._write(closed)

            # Open new bar
            if tf not in active:
                active[tf] = Bar(symbol=symbol, timeframe=tf, ts_open=bar_ts)

            active[tf].update(price, volume, ticks)

    async def _write(self, bar: Bar) -> None:
        if self._qdb is None:
            return
        try:
            writer = getattr(self._qdb, "_writer", None)
            if writer and not writer.is_closing():
                writer.write(bar.to_ilp().encode())
                self._bars_written += 1
        except Exception as e:
            logger.error(f"CandleWriter: ILP write failed ({bar.symbol}): {e}")

    @property
    def stats(self) -> dict:
        return {"bars_written": self._bars_written, "active_symbols": len(self._active)}
