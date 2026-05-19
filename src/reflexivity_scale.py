import logging
import math
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class ReflexivityScale:
    """
    Implements George Soros's Reflexivity Theory in quantitative form.
    Markets are NOT efficient: participant beliefs change fundamentals, which in turn
    change participant beliefs — a self-reinforcing feedback loop.

    This module detects when price action is entering a reflexive boom or bust cycle
    by measuring the correlation between price momentum and changes in positioning data.
    """

    def __init__(self, lookback: int = 30) -> None:
        self.lookback = lookback

    def compute_reflexivity_index(
        self,
        prices: List[float],
        positioning: List[float],
    ) -> float:
        """
        Returns a Reflexivity Index from -1.0 (bust spiral) to +1.0 (boom spiral).

        Logic: If price momentum and the rate-of-change of positioning are *both*
        accelerating in the same direction, a self-reinforcing loop is forming.

        :param prices: Raw close prices (at least lookback periods)
        :param positioning: Net speculative positioning (e.g., COT non-commercial net)
        """
        if len(prices) < self.lookback or len(positioning) < self.lookback:
            logger.warning("[REFLEXIVITY] Insufficient data. Returning neutral 0.0.")
            return 0.0

        p = np.array(prices[-self.lookback :])
        pos = np.array(positioning[-self.lookback :])

        # Price momentum: rate of change over the window
        price_roc = (p[-1] - p[0]) / (p[0] if p[0] != 0 else 1.0)

        # Positioning velocity: rate-of-change of COT positioning
        pos_roc = (pos[-1] - pos[0]) / (abs(pos[0]) if pos[0] != 0 else 1.0)

        # Reflexivity = correlated co-movement of belief (positioning) and price
        # If both are strongly positive -> boom spiral forming
        # If both are strongly negative -> bust spiral forming
        index = math.tanh(price_roc * pos_roc * 10.0)

        if abs(index) > 0.7:
            spiral = "BOOM" if index > 0 else "BUST"
            logger.warning(f"[REFLEXIVITY] {spiral} spiral detected. Index={index:.3f}")

        return float(index)

    def is_spiral_forming(
        self, prices: List[float], positioning: List[float], threshold: float = 0.6
    ) -> bool:
        idx = self.compute_reflexivity_index(prices, positioning)
        return abs(idx) >= threshold
