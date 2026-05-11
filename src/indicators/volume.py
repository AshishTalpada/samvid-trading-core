"""src/indicators/volume.py — VWAP"""

from __future__ import annotations


class VWAP:
    """
    Volume-Weighted Average Price.
    Resets at each new session (call reset() at market open).
    """

    def __init__(self) -> None:
        self._cum_pv = 0.0  # cumulative price * volume
        self._cum_v = 0.0  # cumulative volume
        self.initialized = False

    def update(self, price: float, volume: float) -> float | None:
        if volume <= 0:
            return self.value

        # Optimization: use local variables for hot-path arithmetic
        new_v = self._cum_v + volume
        new_pv = self._cum_pv + (price * volume)

        self._cum_pv = new_pv
        self._cum_v = new_v

        if self._cum_v > 0:
            self.initialized = True
            self._cached_value = self._cum_pv / self._cum_v
            return self._cached_value
        return None

    @property
    def value(self) -> float | None:
        if not self.initialized:
            return None
        return getattr(self, "_cached_value", None)

    def reset(self) -> None:
        """Call at market open each day."""
        self._cum_pv = 0.0
        self._cum_v = 0.0
        self.initialized = False
