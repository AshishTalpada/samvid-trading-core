from typing import List

import numpy as np


class RegimeAttention:
    """Identifies historical periods most similar to current market state."""
    def __init__(self, top_k: int = 5):
        self.top_k = top_k

    def find_historical_analogues(self, current_features: List[float],
                                  historical_features: List[List[float]],
                                  labels: List[str]) -> List[str]:
        if not historical_features or not labels:
            return []
        curr = np.array(current_features)
        distances = [np.linalg.norm(curr - np.array(h)) for h in historical_features]
        sorted_idx = np.argsort(distances)[:self.top_k]
        return [labels[i] for i in sorted_idx]
