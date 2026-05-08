import numpy as np
from typing import List

class RegimeClusterer:
    """Discovers market regimes via k-means clustering on return/vol data."""
    def __init__(self, k: int = 4):
        self.k = k
        self.centroids: List[np.ndarray] = []

    def fit(self, features: List[List[float]]) -> List[int]:
        """Returns cluster labels for each data point."""
        if len(features) < self.k:
            return [0] * len(features)
        X = np.array(features)
        idx = np.random.choice(len(X), self.k, replace=False)
        self.centroids = [X[i] for i in idx]
        labels = [0] * len(X)
        for _ in range(50):
            for i, point in enumerate(X):
                dists = [np.linalg.norm(point - c) for c in self.centroids]
                labels[i] = int(np.argmin(dists))
            for k in range(self.k):
                pts = X[[j for j, l in enumerate(labels) if l == k]]
                if len(pts) > 0:
                    self.centroids[k] = np.mean(pts, axis=0)
        return labels

    def predict(self, features: List[float]) -> int:
        if not self.centroids:
            return 0
        pt = np.array(features)
        return int(np.argmin([np.linalg.norm(pt - c) for c in self.centroids]))
