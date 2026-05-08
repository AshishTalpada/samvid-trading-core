import logging

import numpy as np

logger = logging.getLogger(__name__)

class DynamicKelly:
    """Kelly Criterion position sizer using Shannon Entropy of win probability."""
    def __init__(self, max_kelly_fraction: float = 0.25):
        self.max_kelly = max_kelly_fraction

    def calculate(self, win_prob: float, win_loss_ratio: float) -> float:
        if win_loss_ratio <= 0 or win_prob <= 0:
            return 0.0
        kelly = win_prob - (1 - win_prob) / win_loss_ratio
        if kelly <= 0:
            return 0.0
        # Use half-Kelly for safety
        fraction = min(kelly * 0.5, self.max_kelly)
        logger.debug(f"Kelly fraction: {fraction:.3f} (win_prob={win_prob:.2f}, ratio={win_loss_ratio:.2f})")
        return round(fraction, 4)
