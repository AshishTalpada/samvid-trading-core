import logging
from collections import defaultdict
from typing import Dict, List

import numpy as np

logger = logging.getLogger(__name__)

class CapitalFlowAgent:
    """
    Graph Attention Network-inspired capital flow tracker.
    Detects sector rotation by tracking relative strength flows between tickers.
    Identifies leader-follower relationships in real time.
    """
    def __init__(self):
        self._returns: dict[str, list[float]] = defaultdict(list)

    def ingest(self, ticker: str, ret: float):
        buf = self._returns[ticker]
        buf.append(ret)
        if len(buf) > 60:
            buf.pop(0)

    def compute_flow_matrix(self) -> dict[str, dict[str, float]]:
        tickers = list(self._returns.keys())
        flow: dict[str, dict[str, float]] = {}
        for t1 in tickers:
            flow[t1] = {}
            r1 = np.array(self._returns[t1])
            for t2 in tickers:
                if t1 == t2: continue
                r2 = np.array(self._returns[t2])
                n = min(len(r1), len(r2))
                if n < 5: flow[t1][t2] = 0.0; continue
                corr = float(np.corrcoef(r1[-n:], r2[-n:])[0,1])
                lead_score = float(np.corrcoef(r1[-n:-1], r2[-(n-1):])[0,1]) - corr
                flow[t1][t2] = round(lead_score, 4)
        return flow

    def get_leaders(self, top_n: int = 3) -> list[str]:
        matrix = self.compute_flow_matrix()
        scores = {t: sum(v for v in leads.values()) for t, leads in matrix.items()}
        return sorted(scores, key=scores.get, reverse=True)[:top_n]  # type: ignore
