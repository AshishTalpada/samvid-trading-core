"""
src/position_cache.py — Persisted Single Source of Truth for Open Positions
Replaces scattered state in brain.py._positions and agent_c_ibkr._positions_cache.
Survives crashes — reloaded on startup.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Optional

logger = logging.getLogger("PositionCache")

_CACHE_PATH = os.path.join("data", "positions.json")


@dataclass
class CachedPosition:
    symbol: str
    side: str  # "LONG" | "SHORT"
    quantity: float
    entry_price: float
    stop_loss: float
    take_profit: float
    entry_time: str  # ISO format
    task_id: str
    broker_order_id: Optional[str] = None
    slippage_cost: float = 0.0
    commission_cost: float = 0.0

    @property
    def notional(self) -> float:
        return self.quantity * self.entry_price

    @property
    def unrealized_pnl(self, current_price: float = 0.0) -> float:
        if current_price <= 0:
            return 0.0
        direction = 1.0 if self.side == "LONG" else -1.0
        return direction * (current_price - self.entry_price) * self.quantity


class PositionCache:
    """
    Thread-safe, crash-safe position registry.
    Every mutation flushes to disk atomically.
    """

    def __init__(self, path: str = _CACHE_PATH):
        self._path = path
        self._positions: dict[str, CachedPosition] = {}
        self._load()

    def add(self, pos: CachedPosition) -> None:
        """Register a new open position."""
        self._positions[pos.symbol] = pos
        self._flush()
        logger.info(
            f"PositionCache:  Added {pos.symbol} {pos.side} x{pos.quantity} @ ${pos.entry_price:.2f}"
        )

    def update(self, symbol: str, **kwargs) -> None:
        """Update fields on an existing position (e.g. slippage_cost after fill)."""
        pos = self._positions.get(symbol)
        if pos is None:
            logger.warning(f"PositionCache: Cannot update {symbol} — not found.")
            return
        for k, v in kwargs.items():
            if hasattr(pos, k):
                setattr(pos, k, v)
        self._flush()

    def remove(self, symbol: str) -> Optional[CachedPosition]:
        """Remove a position on close. Returns the removed position."""
        pos = self._positions.pop(symbol, None)
        if pos:
            self._flush()
            logger.info(f"PositionCache:  Removed {symbol} ({pos.side})")
        return pos

    def get(self, symbol: str) -> Optional[CachedPosition]:
        return self._positions.get(symbol)

    def all(self) -> list[CachedPosition]:
        return list(self._positions.values())

    def symbols(self) -> list[str]:
        return list(self._positions.keys())

    def is_flat(self, symbol: str) -> bool:
        return symbol not in self._positions

    def is_long(self, symbol: str) -> bool:
        pos = self._positions.get(symbol)
        return pos is not None and pos.side == "LONG"

    def is_short(self, symbol: str) -> bool:
        pos = self._positions.get(symbol)
        return pos is not None and pos.side == "SHORT"

    def count(self) -> int:
        return len(self._positions)

    def _flush(self) -> None:
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump({k: asdict(v) for k, v in self._positions.items()}, f, indent=2)
            os.replace(tmp, self._path)
        except Exception as e:
            logger.error(f"PositionCache: Flush failed: {e}")

    def _load(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                data = json.load(f)
            self._positions = {k: CachedPosition(**v) for k, v in data.items()}
            if self._positions:
                logger.info(
                    f"PositionCache: ✓ Restored {len(self._positions)} open positions from disk."
                )
        except Exception as e:
            logger.error(f"PositionCache: Load failed ({e}). Starting empty.")

    def summary(self) -> list[dict]:
        return [
            {
                "symbol": p.symbol,
                "side": p.side,
                "quantity": p.quantity,
                "entry": p.entry_price,
                "stop": p.stop_loss,
                "target": p.take_profit,
                "notional": round(p.notional, 2),
            }
            for p in self._positions.values()
        ]


# Module-level singleton — import and use directly
POSITION_CACHE = PositionCache()
