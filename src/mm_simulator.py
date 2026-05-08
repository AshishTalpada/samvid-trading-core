import logging

import numpy as np

logger = logging.getLogger(__name__)

class MarketMakerSimulator:
    """
    Simulates market-maker stop-hunt behaviour.
    MMs identify retail stop clusters (round numbers, recent swing lows/highs)
    and temporarily push price through them to collect stop orders before reversing.
    Sovereign uses this to avoid placing stops at predictable levels.
    """
    def identify_stop_clusters(self, prices: list[float], round_factor: float = 0.5) -> list[float]:
        """Returns price levels where retail stops likely cluster."""
        arr = np.array(prices)
        clusters = []
        # Round numbers (e.g., 150.00, 149.50)
        p_min, p_max = arr.min(), arr.max()
        level = round(p_min / round_factor) * round_factor
        while level <= p_max:
            clusters.append(round(float(level), 2))
            level += round_factor
        # Recent swing lows / highs
        for i in range(2, len(arr)-2):
            if arr[i] < arr[i-1] and arr[i] < arr[i+1] and arr[i] < arr[i-2] and arr[i] < arr[i+2]:
                clusters.append(float(arr[i]))
            if arr[i] > arr[i-1] and arr[i] > arr[i+1] and arr[i] > arr[i-2] and arr[i] > arr[i+2]:
                clusters.append(float(arr[i]))
        return sorted(set(round(c, 2) for c in clusters))

    def safe_stop_level(self, entry: float, side: str, prices: list[float], buffer_pct: float = 0.003) -> float:
        clusters = self.identify_stop_clusters(prices)
        if side == "long":
            candidates = [c for c in clusters if c < entry]
            if not candidates: return entry * (1 - 0.01)
            nearest = max(candidates)
            return nearest * (1 - buffer_pct)
        else:
            candidates = [c for c in clusters if c > entry]
            if not candidates: return entry * (1 + 0.01)
            nearest = min(candidates)
            return nearest * (1 + buffer_pct)
