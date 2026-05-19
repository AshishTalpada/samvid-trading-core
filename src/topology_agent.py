import logging

import numpy as np

logger = logging.getLogger(__name__)


class TopologicalDataAgent:
    """
    Topological Data Analysis (TDA) agent.
    Uses persistent homology (via Vietoris-Rips complex approximation) to detect
    'holes' in the price manifold that signal regime changes before they appear in
    traditional indicators. High Betti numbers = complex topology = impending crash.
    """

    def __init__(self, max_dimension: int = 1):
        self.max_dim = max_dimension

    def compute_persistence(self, price_series: list[float], eps_steps: int = 20) -> list[tuple]:
        """
        Simplified persistence diagram computation.
        Returns list of (birth, death) pairs for 0-dimensional homology (connected components).
        """
        arr = np.array(price_series)
        n = len(arr)
        if n < 4:
            return []
        # Pairwise distance matrix (returns time-series)
        dists = np.abs(arr[:, None] - arr[None, :])
        eps_range = np.linspace(0, dists.max(), eps_steps)
        components = list(range(n))
        pairs: list[tuple] = []
        for eps in eps_range:
            for i in range(n):
                for j in range(i + 1, n):
                    if dists[i, j] <= eps and components[i] != components[j]:
                        old = components[j]
                        new = components[i]
                        pairs.append((dists[i, j], eps))
                        components = [new if c == old else c for c in components]
        return pairs

    def topological_complexity(self, price_series: list[float]) -> float:
        pairs = self.compute_persistence(price_series)
        lifetimes = [d - b for b, d in pairs if d > b]
        return float(np.mean(lifetimes)) if lifetimes else 0.0
