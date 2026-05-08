import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

class NeuralScentDetector:
    """
    Detects the 'smell' of a breakout before volume arrives.
    Analyzes micro-structure anomalies (e.g. shrinking bid-ask spread combined
    with tiny aggressive sweeps) that precede a massive institutional order.
    """
    def __init__(self, sensitivity: float = 2.0):
        self.sensitivity = sensitivity

    def detect_scent(self, spreads: List[float], aggressive_buy_ratios: List[float]) -> float:
        if len(spreads) < 10 or len(aggressive_buy_ratios) < 10:
            return 0.0

        spread_compression = spreads[0] / (np.mean(spreads[-3:]) + 1e-9)
        agg_buying = np.mean(aggressive_buy_ratios[-3:])

        # High scent if spread compresses AND aggressive buying increases
        scent_score = spread_compression * agg_buying * self.sensitivity

        if scent_score > 3.0:
            logger.info(f"[SCENT] High breakout probability detected. Scent={scent_score:.2f}")

        return float(min(1.0, scent_score / 5.0)) # Normalize 0 to 1
