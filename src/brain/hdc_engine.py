import numpy as np


class HDCEngine:
    """Represents signals as 10,000-bit hyperdimensional vectors for ultra-fast comparison."""
    DIMS = 10000

    def encode(self, signal_values: list[float]) -> np.ndarray:
        rng = np.random.default_rng(seed=int(sum(signal_values) * 1000) % (2**31))
        hv = rng.integers(0, 2, self.DIMS, dtype=np.int8)
        hv[hv == 0] = -1
        return hv

    def similarity(self, hv1: np.ndarray, hv2: np.ndarray) -> float:
        return float(np.dot(hv1, hv2) / self.DIMS)
