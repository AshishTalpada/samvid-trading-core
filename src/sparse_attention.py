import numpy as np

class SparseAttention:
    def __init__(self, sparsity_threshold: float = 0.01):
        self.threshold = sparsity_threshold

    def filter_bars(self, bars: list[float]) -> list[float]:
        if not bars: return []
        filtered = [bars[0]]
        for val in bars[1:]:
            if abs(val - filtered[-1]) / (abs(filtered[-1]) + 1e-9) > self.threshold:
                filtered.append(val)
        return filtered
