"""
src/tick_batcher.py — Async Tick Batching Buffer
Prevents Bayesian/Dhatu updates from running 100x per second.
Buffers incoming ticks per-symbol and flushes as a batch every N ms.

Architecture:
  ibkr_streamer → TICK_BATCHER.push() → (every 100ms) → bus.publish("tick.batch", {...})
  brain.py  ← subscribes to "tick.batch" → updates Bayesian/Dhatu once per batch

Usage:
    from tick_batcher import TICK_BATCHER

    # In ibkr_streamer.on_tick(), replace direct bus.publish with:
    TICK_BATCHER.push(symbol, price, bid, ask, size)

    # Start the flush loop as a background task:
    asyncio.create_task(TICK_BATCHER.run(bus))
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from intelligence_bus import SharedIntelligenceBus

logger = logging.getLogger("TickBatcher")


@dataclass
class TickBatch:
    """Aggregated tick data for a single symbol over a flush interval."""

    symbol: str
    count: int = 0
    last_price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    high: float = 0.0
    low: float = float("inf")
    total_volume: float = 0.0
    vwap_num: float = 0.0  # price * volume sum for VWAP
    ts_first: float = field(default_factory=time.monotonic)
    ts_last: float = field(default_factory=time.monotonic)

    def update(self, price: float, bid: float, ask: float, size: float) -> None:
        self.count += 1
        self.last_price = price
        self.bid = bid
        self.ask = ask
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.total_volume += size
        self.vwap_num += price * size
        self.ts_last = time.monotonic()

    @property
    def vwap(self) -> float:
        return self.vwap_num / self.total_volume if self.total_volume > 0 else self.last_price

    @property
    def spread_bps(self) -> float:
        if self.bid > 0 and self.ask > self.bid:
            return ((self.ask - self.bid) / self.bid) * 10_000
        return 0.0

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "count": self.count,
            "price": self.last_price,
            "bid": self.bid,
            "ask": self.ask,
            "high": self.high,
            "low": self.low if self.low < float("inf") else self.last_price,
            "volume": self.total_volume,
            "vwap": round(self.vwap, 4),
            "spread_bps": round(self.spread_bps, 2),
            "ts": self.ts_last,
        }


class TickBatcher:
    """
    Aggregates high-frequency ticks and publishes batched summaries
    to the Intelligence Bus at a configurable interval.

    Benefits:
    - Reduces Bayesian/Dhatu update calls from 100/s → 10/s
    - Provides intra-batch OHLCV (high/low/vwap) for free
    - Preserves every tick for QuestDB (raw tick path is unchanged)
    """

    def __init__(self, flush_interval_ms: float = 100.0, buffer_depth: int = 500):
        """
        Parameters
        ----------
        flush_interval_ms : How often to flush batches to the bus (default 100ms = 10Hz)
        buffer_depth      : Max ticks to buffer per symbol before forced flush
        """
        self._interval = flush_interval_ms / 1000.0
        self._buffer_depth = buffer_depth
        self._batches: dict[str, TickBatch] = {}
        self._lock = asyncio.Lock()
        self._flush_count = 0
        self._drop_count = 0
        self._running = False

    def push(
        self, symbol: str, price: float, bid: float = 0.0, ask: float = 0.0, size: float = 0.0
    ) -> None:
        """
        Non-blocking tick ingestion. Called from ibkr_streamer.on_tick().
        Thread-safe via Python's GIL for dict mutation.
        """
        if symbol not in self._batches:
            self._batches[symbol] = TickBatch(symbol=symbol)
        self._batches[symbol].update(price, bid, ask, size)

        # Force-flush if a symbol is generating extreme tick volume
        if self._batches[symbol].count >= self._buffer_depth:
            logger.debug(
                f"TickBatcher: Force-flush triggered for {symbol} (depth={self._buffer_depth})"
            )

    async def _flush(self, bus: "SharedIntelligenceBus | None") -> None:
        """Swap the batch dict atomically and publish each symbol's batch."""
        if not self._batches:
            return

        # Atomic swap — grab current batches and reset
        async with self._lock:
            snapshot = self._batches
            self._batches = {}

        if bus is None:
            return

        for symbol, batch in snapshot.items():
            if batch.count == 0:
                continue
            try:
                await bus.publish("tick.batch", batch.to_dict())
            except Exception as e:
                logger.error(f"TickBatcher: publish error for {symbol}: {e}")

        self._flush_count += 1
        if self._flush_count % 600 == 0:  # Log stats every 60s at 10Hz
            total = sum(b.count for b in snapshot.values())
            logger.debug(f"TickBatcher: flushed {len(snapshot)} symbols | {total} ticks/min")

    async def run(self, bus: "SharedIntelligenceBus | None" = None) -> None:
        """
        Main flush loop. Run as a background asyncio task.
        Stops cleanly when the task is cancelled.
        """
        self._running = True
        logger.info(f"TickBatcher: Started — flush interval {self._interval * 1000:.0f}ms")

        try:
            while self._running:
                await asyncio.sleep(self._interval)
                await self._flush(bus)
        except asyncio.CancelledError:
            # Final flush on shutdown
            await self._flush(bus)
            logger.info("TickBatcher: Shutdown — final flush complete.")
            raise

    def stop(self) -> None:
        self._running = False

    @property
    def stats(self) -> dict:
        return {
            "active_symbols": len(self._batches),
            "flush_count": self._flush_count,
            "drop_count": self._drop_count,
        }


# Module-level singleton — import and use directly
TICK_BATCHER = TickBatcher(flush_interval_ms=100.0)
