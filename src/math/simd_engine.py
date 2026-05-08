import numpy as np

class SIMDMathEngine:
    """Utilizes AVX-512 instructions via NumPy for microsecond math."""
    def vectorized_log_returns(self, prices: np.ndarray) -> np.ndarray:
        if len(prices) < 2:
            return np.array([])
        return np.diff(np.log(prices))
