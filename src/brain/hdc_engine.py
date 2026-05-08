import logging

import numpy as np

logger = logging.getLogger(__name__)

class HDCEngine:
    """
    Hyperdimensional Computing engine (10,000-dim binary vectors).
    Encodes market regimes as hypervectors; classifies new conditions
    via Hamming distance — nanosecond inference without GPU.
    """
    DIM = 10_000

    def __init__(self):
        rng = np.random.default_rng(seed=42)
        self._memory: dict[str, np.ndarray] = {}
        self._rng = rng

    def encode(self, features: dict[str, float]) -> np.ndarray:
        acc = np.zeros(self.DIM, dtype=np.int32)
        for key, val in features.items():
            if key not in self._memory:
                self._memory[key] = self._rng.integers(0, 2, self.DIM, dtype=np.int32) * 2 - 1
            level = max(0, min(9, int(val * 10)))
            shifted = np.roll(self._memory[key], level)
            acc += shifted
        return (acc > 0).astype(np.uint8)

    def classify(self, query: np.ndarray, prototypes: dict[str, np.ndarray]) -> str:
        best, best_sim = "UNKNOWN", -1.0
        for label, proto in prototypes.items():
            sim = 1.0 - np.sum(query != proto) / self.DIM
            if sim > best_sim:
                best, best_sim = label, sim
        logger.debug(f"[HDC] Classified as '{best}' (sim={best_sim:.3f})")
        return best
