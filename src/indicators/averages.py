"""src/indicators/averages.py — EMA, SMA, WMA"""
from __future__ import annotations

from collections import deque


class EMA:
    """Exponential Moving Average — O(1) incremental update."""
    def __init__(self, period: int):
        self.period = period
        self._alpha = 2.0 / (period + 1)
        self._value: float | None = None
        self._count = 0
        self.initialized = False

    def update(self, price: float) -> float | None:
        self._count += 1
        if self._value is None:
            self._value = price
        else:
            self._value = self._alpha * price + (1.0 - self._alpha) * self._value
        if self._count >= self.period:
            self.initialized = True
        return self._value if self.initialized else None

    @property
    def value(self) -> float | None:
        return self._value if self.initialized else None

    def reset(self) -> None:
        self._value = None
        self._count = 0
        self.initialized = False


class SMA:
    """Simple Moving Average using a fixed-size deque."""
    def __init__(self, period: int):
        self.period = period
        self._buf: deque[float] = deque(maxlen=period)
        self.initialized = False

    def update(self, price: float) -> float | None:
        self._buf.append(price)
        if len(self._buf) == self.period:
            self.initialized = True
        return sum(self._buf) / len(self._buf) if self.initialized else None

    @property
    def value(self) -> float | None:
        if not self.initialized:
            return None
        return sum(self._buf) / self.period

    def reset(self) -> None:
        self._buf.clear()
        self.initialized = False


class WMA:
    """Weighted Moving Average — linearly weighted, most recent gets highest weight."""
    def __init__(self, period: int):
        self.period = period
        self._buf: deque[float] = deque(maxlen=period)
        self._denom = period * (period + 1) / 2
        self.initialized = False

    def update(self, price: float) -> float | None:
        self._buf.append(price)
        if len(self._buf) == self.period:
            self.initialized = True
        if not self.initialized:
            return None
        weighted = sum(p * (i + 1) for i, p in enumerate(self._buf))
        return weighted / self._denom

    def reset(self) -> None:
        self._buf.clear()
        self.initialized = False
