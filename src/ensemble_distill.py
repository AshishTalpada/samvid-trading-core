import numpy as np

class EnsembleDistiller:
    def distill(self, weight_matrices: list[np.ndarray]) -> np.ndarray:
        if not weight_matrices: return np.array([])
        return np.mean(weight_matrices, axis=0)
