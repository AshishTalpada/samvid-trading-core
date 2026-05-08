import numpy as np

class ScentDetector:
    """Detects early breakout conditions before volume confirms the move."""
    def __init__(self, vol_ratio_threshold: float = 1.5, price_compression_threshold: float = 0.005):
        self.vol_ratio_threshold = vol_ratio_threshold
        self.price_compression = price_compression_threshold

    def detect(self, recent_volumes: list[float], recent_highs: list[float],
               recent_lows: list[float]) -> bool:
        if len(recent_volumes) < 10:
            return False
        avg_vol = np.mean(recent_volumes[:-3])
        recent_vol = np.mean(recent_volumes[-3:])
        vol_ratio = recent_vol / avg_vol if avg_vol > 0 else 1.0

        compression = np.mean(np.array(recent_highs[-5:]) - np.array(recent_lows[-5:]))
        avg_range = np.mean(np.array(recent_highs) - np.array(recent_lows))
        price_compressed = compression < avg_range * (1 - self.price_compression)

        return vol_ratio > self.vol_ratio_threshold and price_compressed
