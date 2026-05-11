"""src/indicators/volatility.py — ATR, BollingerBands, KeltnerChannel"""

from __future__ import annotations

from collections import deque

from indicators.averages import EMA, SMA


class ATR:
    """Average True Range (Wilder's smoothing)."""

    def __init__(self, period: int = 14):
        self.period = period
        self._prev_close: float | None = None
        self._atr: float | None = None
        self._count = 0
        self._buf: deque[float] = deque(maxlen=period)
        self.initialized = False

    def update(self, high: float, low: float, close: float) -> float | None:
        if self._prev_close is None:
            self._prev_close = close
            return None

        tr = max(
            high - low,
            abs(high - self._prev_close),
            abs(low - self._prev_close),
        )
        self._prev_close = close
        self._buf.append(tr)

        if len(self._buf) < self.period:
            return None

        if not self.initialized:
            self._atr = sum(self._buf) / self.period
            self.initialized = True
        else:
            alpha = 1.0 / self.period
            self._atr = alpha * tr + (1.0 - alpha) * self._atr  # type: ignore

        return self._atr

    def reset(self) -> None:
        self._prev_close = None
        self._atr = None
        self._buf.clear()
        self.initialized = False


class BollingerBands:
    """Bollinger Bands: middle SMA ± k * std."""

    def __init__(self, period: int = 20, k: float = 2.0):
        self.period = period
        self.k = k
        self._sma = SMA(period)
        self._buf: deque[float] = deque(maxlen=period)
        self._sum_sq = 0.0
        self.initialized = False

    def update(self, price: float) -> tuple[float, float, float] | None:
        """Returns (upper, middle, lower) or None."""
        if len(self._buf) == self.period:
            old_price = self._buf[0]
            self._sum_sq -= old_price**2

        self._buf.append(price)
        self._sum_sq += price**2

        mid = self._sma.update(price)
        if mid is None:
            return None

        # Var = E[X^2] - (E[X])^2
        mean_sq = self._sum_sq / len(self._buf)
        variance = max(0, mean_sq - mid**2)
        import math
        std = math.sqrt(variance)
        self.initialized = True
        return mid + self.k * std, mid, mid - self.k * std

    def reset(self) -> None:
        self._sma.reset()
        self._buf.clear()
        self._sum_sq = 0.0
        self.initialized = False


class KeltnerChannel:
    """Keltner Channel: EMA ± k * ATR."""

    def __init__(self, period: int = 20, atr_period: int = 10, k: float = 2.0):
        self.k = k
        self._ema = EMA(period)
        self._atr = ATR(atr_period)
        self.initialized = False

    def update(self, high: float, low: float, close: float) -> tuple[float, float, float] | None:
        """Returns (upper, middle, lower) or None."""
        mid = self._ema.update(close)
        atr_val = self._atr.update(high, low, close)
        if mid is None or atr_val is None:
            return None
        self.initialized = True
        return mid + self.k * atr_val, mid, mid - self.k * atr_val

    def reset(self) -> None:
        self._ema.reset()
        self._atr.reset()
        self.initialized = False
