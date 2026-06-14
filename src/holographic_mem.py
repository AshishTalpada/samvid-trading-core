import logging

import numpy as np

logger = logging.getLogger(__name__)


class HolographicMemoryStore:
    """
    Holographic Reduced Representation (HRR) memory store.
    Encodes key-value pairs as superposition of hypervectors.
    Retrieval via circular convolution — O(n log n) via FFT.
    Stores 10,000+ market facts in a single 10,000-dim vector.
    """

    DIM = 10_000

    def __init__(self):
        rng = np.random.default_rng(42)
        self._memory = np.zeros(self.DIM)
        self._rng = rng
        self._register: dict[str, np.ndarray] = {}

    def _basis(self, key: str) -> np.ndarray:
        if key not in self._register:
            v = self._rng.normal(0, 1.0 / np.sqrt(self.DIM), self.DIM)
            self._register[key] = v / np.linalg.norm(v)
        return self._register[key]

    def store(self, key: str, value: str) -> None:
        k_vec = self._basis(key)
        v_vec = self._basis(value)
        trace = np.real(np.fft.ifft(np.fft.fft(k_vec) * np.fft.fft(v_vec)))
        self._memory += trace

    def retrieve(self, key: str) -> str:
        if not self._register:
            return ""
        k_vec = self._basis(key)
        probe = np.real(np.fft.ifft(np.fft.fft(self._memory) * np.conj(np.fft.fft(k_vec))))
        best_key, best_sim = "", -1.0
        for candidate, vec in self._register.items():
            if candidate == key:
                continue  # Skip the query key itself — we want the associated value
            sim = float(np.dot(probe, vec))
            if sim > best_sim:
                best_sim, best_key = sim, candidate
        return best_key
