"""Live market microstructure signals computed from tick and order-book data.

Provides a hawk-eye view of the present market: spread, mid price, VWAP,
tape speed, large-lot prints, order-flow imbalance, and volume-at-price
clusters.  Designed to feed the TradeInterrogator and coordinator veto
chain with sub-second market state.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Tick:
    """Normalised tick event."""

    price: float
    size: float
    timestamp: float
    bid: float = 0.0
    ask: float = 0.0
    is_buy: bool | None = None


@dataclass
class MicrostructureSnapshot:
    """Computed microstructure signals for a single symbol."""

    symbol: str
    last_price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    spread: float = 0.0
    spread_pct: float = 0.0
    mid: float = 0.0
    vwap: float = 0.0
    tape_speed_30s: float = 0.0
    large_lot_pressure: float = 0.0  # positive = buy-side, negative = sell-side
    book_imbalance: float = 0.0  # range [-1, 1]
    volume_at_price: float = 0.0
    abnormal_volume: bool = False
    last_update: float = 0.0


class MarketMicrostructure:
    """Compute real-time market microstructure signals from streaming ticks."""

    def __init__(self, max_symbols: int = 50, tick_window: int = 2000):
        self.max_symbols = max_symbols
        self.tick_window = tick_window
        self._ticks: dict[str, deque[Tick]] = {}
        self._snapshot: dict[str, MicrostructureSnapshot] = {}
        self._large_lot_threshold: float = 100.0
        self._last_pruned = time.monotonic()

    def _ensure_symbol(self, symbol: str) -> None:
        if symbol not in self._ticks:
            # If we are already at the limit, prune oldest immediately.
            if len(self._ticks) >= self.max_symbols:
                self._prune_oldest(force=True)
            self._ticks[symbol] = deque(maxlen=self.tick_window)
            self._snapshot[symbol] = MicrostructureSnapshot(symbol=symbol)

    def _prune_oldest(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self._last_pruned < 5.0:
            return
        self._last_pruned = now
        oldest = sorted(
            self._snapshot.items(),
            key=lambda kv: kv[1].last_update or 0,
        )
        # Remove enough symbols to get back under the limit, or 10% if periodic cleanup.
        over_limit = len(oldest) - self.max_symbols + 1 if len(oldest) >= self.max_symbols else 0
        remove_count = max(over_limit, len(oldest) // 10) if len(oldest) > 0 else 0
        for sym, _ in oldest[: max(1, remove_count)]:
            self._ticks.pop(sym, None)
            self._snapshot.pop(sym, None)

    def on_tick(self, data: dict[str, Any]) -> None:
        """Ingest a tick event.

        Expected keys: symbol, price, size (optional), bid (optional), ask (optional),
        timestamp (optional).
        """
        symbol = data.get("symbol")
        price = data.get("price")
        if not symbol or price is None:
            return

        self._ensure_symbol(symbol)
        now = data.get("timestamp") or time.monotonic()
        bid = float(data.get("bid", price))
        ask = float(data.get("ask", price))
        size = float(data.get("size", 0.0))

        # Infer buy/sell side from mid if not provided.
        mid = (bid + ask) / 2.0 if bid and ask else float(price)
        is_buy = data.get("is_buy")
        if is_buy is None and bid and ask:
            is_buy = float(price) >= mid

        tick = Tick(
            price=float(price),
            size=size,
            timestamp=now,
            bid=bid,
            ask=ask,
            is_buy=is_buy,
        )
        self._ticks[symbol].append(tick)
        self._recompute(symbol)

    def _recompute(self, symbol: str) -> None:
        ticks = list(self._ticks[symbol])
        if not ticks:
            return

        last = ticks[-1]
        now = time.monotonic()
        mid = (last.bid + last.ask) / 2.0 if last.bid and last.ask else last.price
        spread = abs(last.ask - last.bid) if last.bid and last.ask else 0.0
        spread_pct = spread / mid if mid else 0.0

        # VWAP over the buffered window.
        total_volume = sum(t.size for t in ticks if t.size)
        vwap = (
            sum(t.price * t.size for t in ticks if t.size) / total_volume
            if total_volume > 0
            else last.price
        )

        # Tape speed: trades per second over the last 30 seconds.
        cutoff = now - 30.0
        recent_ticks = [t for t in ticks if t.timestamp >= cutoff]
        tape_speed = len(recent_ticks) / 30.0 if recent_ticks else 0.0

        # Large-lot pressure and volume-at-price clusters.
        buy_pressure = 0.0
        sell_pressure = 0.0
        volume_at_price = 0.0
        for t in ticks:
            if t.size >= self._large_lot_threshold:
                if t.is_buy:
                    buy_pressure += t.size
                else:
                    sell_pressure += t.size
            if abs(t.price - last.price) <= 0.05 * last.price:
                volume_at_price += t.size
        large_lot_pressure = buy_pressure - sell_pressure
        total_large = buy_pressure + sell_pressure or 1.0
        book_imbalance = (buy_pressure - sell_pressure) / total_large

        # Abnormal volume: current 30s volume > 2x median 30s volume over window.
        windowed_volumes = []
        for i in range(0, len(ticks) - len(recent_ticks) + 1, len(recent_ticks) or 1):
            window = ticks[i : i + len(recent_ticks)]
            windowed_volumes.append(sum(t.size for t in window))
        median_volume = sorted(windowed_volumes)[len(windowed_volumes) // 2] if windowed_volumes else 0.0
        current_volume = sum(t.size for t in recent_ticks)
        abnormal_volume = (
            median_volume > 0 and current_volume > 2.0 * median_volume and tape_speed > 1.0
        )

        self._snapshot[symbol] = MicrostructureSnapshot(
            symbol=symbol,
            last_price=last.price,
            bid=last.bid,
            ask=last.ask,
            spread=spread,
            spread_pct=spread_pct,
            mid=mid,
            vwap=vwap,
            tape_speed_30s=tape_speed,
            large_lot_pressure=large_lot_pressure,
            book_imbalance=book_imbalance,
            volume_at_price=volume_at_price,
            abnormal_volume=abnormal_volume,
            last_update=now,
        )

    def get_snapshot(self, symbol: str) -> MicrostructureSnapshot:
        """Return the latest microstructure snapshot for a symbol."""
        return self._snapshot.get(symbol.upper(), MicrostructureSnapshot(symbol=symbol.upper()))

    def get_imbalance(self, symbol: str) -> float:
        """Return order-flow imbalance in range [-1, 1]."""
        return self.get_snapshot(symbol).book_imbalance

    def get_pressure(self, symbol: str) -> float:
        """Return signed large-lot pressure."""
        return self.get_snapshot(symbol).large_lot_pressure

    def get_vwap_deviation(self, symbol: str) -> float:
        """Return price deviation from VWAP as a fraction."""
        snap = self.get_snapshot(symbol)
        if snap.vwap == 0:
            return 0.0
        return (snap.last_price - snap.vwap) / snap.vwap

    def is_liquid(self, symbol: str) -> bool:
        """Return True if spread is tight and tape is active."""
        snap = self.get_snapshot(symbol)
        return snap.spread_pct < 0.002 and snap.tape_speed_30s > 0.5

    def summary(self, symbol: str) -> dict[str, Any]:
        """Return a flat dict for logging / bus messages."""
        snap = self.get_snapshot(symbol)
        return {
            "last_price": snap.last_price,
            "bid": snap.bid,
            "ask": snap.ask,
            "spread": snap.spread,
            "spread_pct": snap.spread_pct,
            "mid": snap.mid,
            "vwap": snap.vwap,
            "vwap_deviation": self.get_vwap_deviation(symbol),
            "tape_speed_30s": snap.tape_speed_30s,
            "large_lot_pressure": snap.large_lot_pressure,
            "book_imbalance": snap.book_imbalance,
            "volume_at_price": snap.volume_at_price,
            "abnormal_volume": snap.abnormal_volume,
            "is_liquid": self.is_liquid(symbol),
        }

    def reset(self, symbol: str) -> None:
        """Clear buffers for a symbol (e.g., after market close)."""
        self._ticks.pop(symbol, None)
        self._snapshot.pop(symbol, None)

    def reset_all(self) -> None:
        """Clear all buffers."""
        self._ticks.clear()
        self._snapshot.clear()

    def __len__(self) -> int:
        return len(self._snapshot)

    def __repr__(self) -> str:
        return f"MarketMicrostructure(symbols={len(self)})"


# Singleton-style global instance for tests and optional direct access.
_GLOBAL_MICROSTRUCTURE: MarketMicrostructure | None = None


def get_global_microstructure() -> MarketMicrostructure:
    global _GLOBAL_MICROSTRUCTURE
    if _GLOBAL_MICROSTRUCTURE is None:
        _GLOBAL_MICROSTRUCTURE = MarketMicrostructure()
    return _GLOBAL_MICROSTRUCTURE


def set_global_microstructure(micro: MarketMicrostructure) -> None:
    global _GLOBAL_MICROSTRUCTURE
    _GLOBAL_MICROSTRUCTURE = micro


def reset_global_microstructure() -> None:
    global _GLOBAL_MICROSTRUCTURE
    _GLOBAL_MICROSTRUCTURE = None


def ingest_tick(data: dict[str, Any]) -> None:
    """Convenience function for direct tick ingestion."""
    get_global_microstructure().on_tick(data)


def get_snapshot(symbol: str) -> MicrostructureSnapshot:
    return get_global_microstructure().get_snapshot(symbol)


def get_summary(symbol: str) -> dict[str, Any]:
    return get_global_microstructure().summary(symbol)


def is_liquid(symbol: str) -> bool:
    return get_global_microstructure().is_liquid(symbol)


def get_imbalance(symbol: str) -> float:
    return get_global_microstructure().get_imbalance(symbol)


def get_vwap_deviation(symbol: str) -> float:
    return get_global_microstructure().get_vwap_deviation(symbol)


def get_pressure(symbol: str) -> float:
    return get_global_microstructure().get_pressure(symbol)


def reset(symbol: str = "") -> None:
    micro = get_global_microstructure()
    if symbol:
        micro.reset(symbol)
    else:
        micro.reset_all()


__all__ = [
    "MarketMicrostructure",
    "MicrostructureSnapshot",
    "Tick",
    "get_global_microstructure",
    "set_global_microstructure",
    "reset_global_microstructure",
    "ingest_tick",
    "get_snapshot",
    "get_summary",
    "is_liquid",
    "get_imbalance",
    "get_vwap_deviation",
    "get_pressure",
    "reset",
]
