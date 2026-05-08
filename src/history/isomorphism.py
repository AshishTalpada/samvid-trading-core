import logging
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)


class IsomorphicPatternMapper:
    """
    Finds repeated mathematical patterns across different assets and market eras.
    Uses Dynamic Time Warping (DTW) distance to match non-linearly scaled analogues.
    Example: 2000 Nasdaq top vs 2021 crypto top vs 1929 Dow top — same topology.
    """

    def dtw_distance(self, s1: List[float], s2: List[float]) -> float:
        n, m = len(s1), len(s2)
        dtw = np.full((n + 1, m + 1), np.inf)
        dtw[0, 0] = 0.0
        for i in range(1, n + 1):
            for j in range(1, m + 1):
                cost = abs(s1[i-1] - s2[j-1])
                dtw[i, j] = cost + min(dtw[i-1, j], dtw[i, j-1], dtw[i-1, j-1])
        return float(dtw[n, m])

    def normalise(self, series: List[float]) -> List[float]:
        arr = np.array(series, dtype=float)
        rng = arr.max() - arr.min()
        return ((arr - arr.min()) / (rng + 1e-9)).tolist()

    def find_best_match(self, query: List[float], archive: Dict[str, List[float]]) -> Dict:
        q = self.normalise(query)
        best_name, best_dist = "none", float("inf")
        for name, series in archive.items():
            dist = self.dtw_distance(q, self.normalise(series))
            if dist < best_dist:
                best_dist = dist
                best_name = name
        logger.info(f"[ISOMORPHISM] Best match: '{best_name}' (DTW={best_dist:.4f})")
        return {"match": best_name, "dtw_distance": round(best_dist, 4)}
