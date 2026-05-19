from typing import List, Tuple

import numpy as np


class IsomorphicMapper:
    """Finds repeated mathematical patterns across different assets and market eras."""

    def __init__(self, tolerance: float = 0.05):
        self.tolerance = tolerance

    def normalize(self, series: List[float]) -> np.ndarray:
        arr = np.array(series, dtype=float)
        rng = arr.max() - arr.min()
        return (arr - arr.min()) / (rng + 1e-9)  # type: ignore

    def find_match(
        self, query: List[float], candidates: List[Tuple[str, List[float]]]
    ) -> List[str]:
        q = self.normalize(query)
        matches = []
        for label, series in candidates:
            if len(series) < len(q):
                continue
            for i in range(len(series) - len(q) + 1):
                window = self.normalize(series[i : i + len(q)])
                if float(np.mean(np.abs(q - window))) < self.tolerance:
                    matches.append(label)
                    break
        return matches
