import numpy as np
from typing import Dict, List

class FeatureCreator:
    """Automatically synthesizes and evaluates new composite technical indicators."""
    def __init__(self):
        self.candidates: Dict[str, float] = {}

    def synthesize(self, prices: List[float], volumes: List[float]) -> Dict[str, float]:
        arr = np.array(prices)
        vol_arr = np.array(volumes)
        features = {
            "price_vol_ratio": float(arr[-1] / np.mean(vol_arr)) if np.mean(vol_arr) > 0 else 0.0,
            "normalized_close": float((arr[-1] - np.min(arr)) / (np.max(arr) - np.min(arr) + 1e-9)),
            "vol_momentum": float(vol_arr[-1] / np.mean(vol_arr[-5:])) if len(vol_arr) >= 5 else 1.0,
            "price_acceleration": float(np.diff(arr)[-1] - np.diff(arr)[-2]) if len(arr) > 2 else 0.0,
        }
        return features
