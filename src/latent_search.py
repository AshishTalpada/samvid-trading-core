import numpy as np

class LatentSpaceSearch:
    def __init__(self, dim: int = 512):
        self.dim = dim

    def find_gap(self, embeddings: list[np.ndarray]) -> np.ndarray:
        if not embeddings:
            return np.zeros(self.dim)
        arr = np.array(embeddings)
        mean_vec = np.mean(arr, axis=0)
        gap = -mean_vec
        return gap / (np.linalg.norm(gap) + 1e-9)
