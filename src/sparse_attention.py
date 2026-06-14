import logging

import numpy as np

logger = logging.getLogger(__name__)


class SparseAttentionEngine:
    """
    Sparse attention mechanism for efficient long-context financial analysis.
    Instead of O(n²) full attention, uses Longformer-style sliding window
    + global attention on key economic events (Fed dates, earnings).
    Enables 100k-token context windows for multi-year pattern analysis.
    """

    def __init__(self, window_size: int = 64, n_global_tokens: int = 8):
        self.window = window_size
        self.n_global = n_global_tokens

    def sliding_window_attention(self, Q: np.ndarray, K: np.ndarray, V: np.ndarray) -> np.ndarray:
        n, d = Q.shape
        output = np.zeros_like(Q)
        if d == 0 or n == 0:
            return output
        sqrt_d = float(np.sqrt(d)) or 1.0
        for i in range(n):
            start = max(0, i - self.window // 2)
            end = min(n, i + self.window // 2 + 1)
            if start >= end:
                continue
            scores = Q[i] @ K[start:end].T / sqrt_d
            weights = np.exp(scores - scores.max())
            weights /= weights.sum() + 1e-9
            output[i] = weights @ V[start:end]
        return output

    def global_token_attention(
        self, Q: np.ndarray, K: np.ndarray, V: np.ndarray, global_indices: list[int]
    ) -> np.ndarray:
        d = Q.shape[-1]
        output = np.zeros_like(Q)
        for i, idx in enumerate(global_indices[: self.n_global]):
            scores = Q[idx] @ K.T / np.sqrt(d)
            weights = np.exp(scores - scores.max())
            weights /= weights.sum() + 1e-9
            output[idx] = weights @ V
        return output
