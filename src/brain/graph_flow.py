from typing import Dict, List

import numpy as np


class GATFlow:
    """Tracks leader-follower relationships between tickers in a sector graph."""
    def __init__(self):
        self.correlation_matrix: Dict[str, Dict[str, float]] = {}

    def update(self, returns: Dict[str, float]) -> None:
        tickers = list(returns.keys())
        for t1 in tickers:
            self.correlation_matrix.setdefault(t1, {})
            for t2 in tickers:
                if t1 != t2:
                    self.correlation_matrix[t1][t2] = 1.0 if (returns[t1] * returns[t2] > 0) else -1.0

    def get_leaders(self, ticker: str, top_n: int = 3) -> List[str]:
        corrs = self.correlation_matrix.get(ticker, {})
        sorted_tickers = sorted(corrs, key=lambda k: corrs[k], reverse=True)
        return sorted_tickers[:top_n]
