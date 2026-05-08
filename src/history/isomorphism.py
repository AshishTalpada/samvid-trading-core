import numpy as np
from typing import List, Tuple

class HistoricalIsomorphism:
    """Finds repeated price patterns across different market eras."""
    def __init__(self, tolerance: float = 0.05):
        self.tolerance = tolerance

    def _normalize(self, series: List[float]) -> np.ndarray:
        arr = np.array(series, dtype=float)
        r = arr.max() - arr.min()
        return (arr - arr.min()) / (r + 1e-9)

    def match(self, query: List[float], history: List[Tuple[str, List[float]]]) -> List[str]:
        q = self._normalize(query)
        matches = []
        for label, series in history:
            if len(series) < len(q):
                continue
            for i in range(len(series) - len(q) + 1):
                window = self._normalize(series[i:i + len(q)])
                if float(np.mean(np.abs(q - window))) < self.tolerance:
                    matches.append(label)
                    break
        return matches
