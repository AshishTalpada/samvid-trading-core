import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class GATFlow:
    """
    Tracks leader-follower relationships between tickers in a sector graph
    using Graph Attention patterns. Maps how capital flows from Mega-caps
    down to Mid-caps to predict delayed breakouts.
    """

    def __init__(self):
        self.flow_matrix: Dict[str, Dict[str, float]] = {}

    def update(self, returns: Dict[str, float]) -> None:
        tickers = list(returns.keys())
        for t1 in tickers:
            if t1 not in self.flow_matrix:
                self.flow_matrix[t1] = {}
            for t2 in tickers:
                if t1 != t2:
                    # Simplified leader-follower: if t1 moves, does t2 follow?
                    direction = 1.0 if (returns[t1] * returns[t2] > 0) else -0.5
                    current = self.flow_matrix[t1].get(t2, 0.0)
                    # Exponential moving average of flow correlation
                    self.flow_matrix[t1][t2] = current * 0.9 + direction * 0.1

    def get_followers(self, leader_ticker: str, threshold: float = 0.6) -> List[str]:
        if leader_ticker not in self.flow_matrix:
            return []

        followers = [t for t, score in self.flow_matrix[leader_ticker].items() if score > threshold]
        if followers:
            logger.debug(
                f"[GAT FLOW] {leader_ticker} leads {len(followers)} tickers: {followers[:3]}"
            )
        return followers
