import numpy as np
import scipy.spatial.distance as dist


class IsomorphicLogic:
    """Finding repeated fractal patterns across different markets/timeframes."""
    def __init__(self, historical_embeddings: np.ndarray):
        self.history = historical_embeddings

    def find_fractal_match(self, current_regime: np.ndarray, tolerance: float = 0.05) -> list[int]:
        """
        Uses dynamic time warping or cosine similarity to find geometrically identical
        setups from 10 years ago, even if the absolute price scale is completely different.
        """
        distances = dist.cdist([current_regime], self.history, metric='cosine')[0]
        # Find indices where cosine distance is less than tolerance (highly isomorphic)
        matches = np.where(distances < tolerance)[0].tolist()
        return matches
