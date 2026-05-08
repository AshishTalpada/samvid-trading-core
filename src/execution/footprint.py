import numpy as np


class FootprintAudit:
    """Detects institutional accumulation by finding large volume with minimal price movement."""
    def __init__(self, price_move_threshold: float = 0.005, min_volume_ratio: float = 2.0):
        self.price_threshold = price_move_threshold
        self.volume_threshold = min_volume_ratio

    def detect_accumulation(self, price_changes: list[float], volumes: list[float],
                            avg_volume: float) -> bool:
        if len(price_changes) < 3 or avg_volume <= 0:
            return False
        for change, vol in zip(price_changes, volumes, strict=False):
            if abs(change) < self.price_threshold and (vol / avg_volume) > self.volume_threshold:
                return True
        return False
