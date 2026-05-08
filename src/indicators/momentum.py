"""src/indicators/momentum.py — RSI, MACD"""

from __future__ import annotations

from collections import deque

from indicators.averages import EMA


class RSI:
    """Wilder's Relative Strength Index — incremental O(1)."""

    def __init__(self, period: int = 14):
        self.period = period
        self._gains: deque[float] = deque(maxlen=period)
        self._losses: deque[float] = deque(maxlen=period)
        self._prev: float | None = None
        self._avg_gain: float | None = None
        self._avg_loss: float | None = None
        self.initialized = False

    def update(self, price: float) -> float | None:
        if self._prev is None:
            self._prev = price
            return None

        change = price - self._prev
        gain = max(change, 0.0)
        loss = abs(min(change, 0.0))
        self._gains.append(gain)
        self._losses.append(loss)
        self._prev = price

        if len(self._gains) < self.period:
            return None

        if not self.initialized:
            self._avg_gain = sum(self._gains) / self.period
            self._avg_loss = sum(self._losses) / self.period
            self.initialized = True
        else:
            alpha = 1.0 / self.period
            self._avg_gain = alpha * gain + (1.0 - alpha) * self._avg_gain  # type: ignore
            self._avg_loss = alpha * loss + (1.0 - alpha) * self._avg_loss  # type: ignore

        if self._avg_loss == 0:
            return 100.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def reset(self) -> None:
        self._gains.clear()
        self._losses.clear()
        self._prev = None
        self._avg_gain = None
        self._avg_loss = None
        self.initialized = False


class MACD:
    """MACD Line, Signal Line, and Histogram."""

    def __init__(self, fast: int = 12, slow: int = 26, signal: int = 9):
        self._fast = EMA(fast)
        self._slow = EMA(slow)
        self._signal = EMA(signal)
        self.initialized = False

    def update(self, price: float) -> tuple[float, float, float] | None:
        """Returns (macd_line, signal_line, histogram) or None if not warmed up."""
        fast_val = self._fast.update(price)
        slow_val = self._slow.update(price)

        if fast_val is None or slow_val is None:
            return None

        macd_line = fast_val - slow_val
        signal_val = self._signal.update(macd_line)

        if signal_val is None:
            return None

        self.initialized = True
        histogram = macd_line - signal_val
        return macd_line, signal_val, histogram

    def reset(self) -> None:
        self._fast.reset()
        self._slow.reset()
        self._signal.reset()
        self.initialized = False
