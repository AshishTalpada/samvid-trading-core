import logging
import math

import numpy as np

logger = logging.getLogger(__name__)

class HyperbolicRiskGeometry:
    """
    Models extreme tail risk events using hyperbolic (non-Euclidean) geometry.
    In Euclidean space, rare events appear far apart. In hyperbolic space,
    exponential tree structure captures the true hierarchy of crash cascades.
    """
    def poincare_distance(self, x: np.ndarray, y: np.ndarray) -> float:
        x_norm = np.linalg.norm(x)
        y_norm = np.linalg.norm(y)
        diff_norm = np.linalg.norm(x - y)
        if x_norm >= 1 or y_norm >= 1: return float("inf")
        num = 2 * diff_norm ** 2
        denom = (1 - x_norm**2) * (1 - y_norm**2)
        return math.acosh(1 + num / (denom + 1e-12))

    def fat_tail_var(self, returns: list[float], confidence: float = 0.99, df: float = 3.0) -> float:
        from scipy import stats
        arr = np.array(returns)
        mu, sigma = float(np.mean(arr)), float(np.std(arr))
        return float(stats.t.ppf(1 - confidence, df=df, loc=mu, scale=sigma))
