import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class RegimeAdaptiveStops:
    """
    ATR-based stop losses that adapt dynamically to BULL/BEAR/VOLATILE regimes.
    A 2x ATR stop in a BULL market is too tight; same stop in VOLATILE is suicidal.
    This engine computes regime-appropriate stop distances.
    """

    REGIME_ATR_MULTIPLIERS = {
        "BULL": 1.5,
        "BEAR": 2.5,
        "VOLATILE": 3.5,
        "CHOPPY": 2.0,
        "UNKNOWN": 2.0,
    }

    def compute_atr(
        self, highs: list[float], lows: list[float], closes: list[float], period: int = 14
    ) -> float:
        if len(highs) < period + 1:
            return 0.0
        true_ranges = []
        for i in range(1, len(highs)):
            tr = max(
                highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1])
            )
            true_ranges.append(tr)
        return float(np.mean(true_ranges[-period:]))

    def stop_distance(self, regime: str, atr: float) -> float:
        mult = self.REGIME_ATR_MULTIPLIERS.get(regime, 2.0)
        return round(atr * mult, 4)

    def compute_stops(
        self,
        entry: float,
        side: str,
        regime: str,
        highs: list[float],
        lows: list[float],
        closes: list[float],
    ) -> dict[str, Any]:
        atr = self.compute_atr(highs, lows, closes)
        dist = self.stop_distance(regime, atr)
        stop = entry - dist if side == "long" else entry + dist
        target_rr = 2.5
        target = entry + dist * target_rr if side == "long" else entry - dist * target_rr
        logger.info(
            f"[REGIME STOPS] {regime} | Entry={entry:.2f} Stop={stop:.2f} Target={target:.2f} ATR={atr:.4f}"
        )
        return {
            "stop_loss": round(stop, 4),
            "take_profit": round(target, 4),
            "atr": round(atr, 4),
            "regime": regime,
        }
