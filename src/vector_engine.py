
import numpy as np


class HyperdimensionalEncoder:
    """
    Hyperdimensional Computing (HDC) engine.
    Encodes market signals as 10,000-bit binary hypervectors.
    Similarity measured via Hamming distance — O(1) inference on CPU.
    """

    DIM = 10_000

    def __init__(self):
        rng = np.random.default_rng(42)
        self._basis: dict[str, np.ndarray] = {}
        self._rng = rng

    def _get_basis(self, key: str) -> np.ndarray:
        if key not in self._basis:
            self._basis[key] = self._rng.integers(0, 2, self.DIM, dtype=np.uint8)
        return self._basis[key]

    def encode_signal(self, features: dict[str, float]) -> np.ndarray:
        hv = np.zeros(self.DIM, dtype=np.int32)
        for key, val in features.items():
            basis = self._get_basis(key)
            level = int(np.clip(val * 10, 0, 9))
            shifted = np.roll(basis, level)
            hv += shifted.astype(np.int32) * 2 - 1
        return (hv > 0).astype(np.uint8)

    def similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        hamming = int(np.sum(a != b))
        return 1.0 - hamming / self.DIM
