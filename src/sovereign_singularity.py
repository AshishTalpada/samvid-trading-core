import logging
import math
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class SovereignSingularityTracker:
    """
    Tracks the approach of the Sovereign Singularity: the point where
    the system's compounding learning rate exceeds market information entropy.
    Monitors: bits-per-trade improvement, entropy reduction over rolling windows.
    """

    def __init__(self):
        self._prediction_errors: list[float] = []
        self._market_entropies: list[float] = []

    def record_trade_error(self, predicted_return: float, actual_return: float) -> None:
        self._prediction_errors.append(abs(predicted_return - actual_return))

    def record_market_entropy(self, returns: list[float]) -> float:
        arr = np.array(returns)
        hist, _ = np.histogram(arr, bins=20, density=True)
        hist = hist[hist > 0]
        h = float(-np.sum(hist * np.log(hist + 1e-9)))
        self._market_entropies.append(h)
        return h

    def singularity_progress(self) -> dict[str, Any]:
        if len(self._prediction_errors) < 20 or len(self._market_entropies) < 20:
            return {"progress": 0.0, "crossed": False}
        learning_rate = 1.0 / (np.mean(self._prediction_errors[-20:]) + 1e-9)
        market_noise = np.mean(self._market_entropies[-20:])
        ratio = float(learning_rate / (market_noise + 1e-9))
        crossed = ratio > 1.0
        if crossed:
            logger.critical(f"[SINGULARITY]  THRESHOLD CROSSED! Ratio={ratio:.4f}")
        return {"ratio": round(ratio, 6), "crossed": crossed,
                "learning_rate": round(float(learning_rate), 4),
                "market_entropy": round(float(market_noise), 4)}
