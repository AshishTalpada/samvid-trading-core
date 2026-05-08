import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

class FeatureCreator:
    """
    Automatically synthesizes and evaluates new composite technical indicators.
    AI discovers alpha by combining raw inputs (price, volume, volatility)
    into non-linear combinations and testing their predictive power.
    """
    def __init__(self):
        self.feature_weights: Dict[str, float] = {}

    def synthesize(self, prices: List[float], volumes: List[float], highs: List[float], lows: List[float]) -> Dict[str, float]:
        if len(prices) < 14:
            return {}

        arr_p = np.array(prices)
        arr_v = np.array(volumes)
        arr_h = np.array(highs)
        arr_l = np.array(lows)

        vol_mean = np.mean(arr_v[-14:]) + 1e-9
        tr = np.maximum(arr_h - arr_l, np.abs(arr_h - np.roll(arr_p, 1)))[1:]
        atr = np.mean(tr[-14:]) + 1e-9

        features = {
            "price_vol_ratio": float(arr_p[-1] / vol_mean),
            "normalized_close": float((arr_p[-1] - np.min(arr_p[-14:])) / (np.max(arr_p[-14:]) - np.min(arr_p[-14:]) + 1e-9)),
            "vol_momentum": float(arr_v[-1] / np.mean(arr_v[-5:]) if len(arr_v) >= 5 else 1.0),
            "price_acceleration": float((arr_p[-1] - 2 * arr_p[-2] + arr_p[-3]) / atr if len(arr_p) >= 3 else 0.0),
            "micro_structure_noise": float(np.std(np.diff(arr_p[-14:])) / atr),
        }

        logger.debug(f"[FEATURE CREATOR] Synthesized {len(features)} composite features")
        return features
