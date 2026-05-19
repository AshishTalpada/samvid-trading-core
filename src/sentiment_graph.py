import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class SentimentGraphAgent:
    """
    Graph Neural Network-inspired sentiment propagation tracker.
    Maps how news sentiment spreads from Reddit → Twitter → Bloomberg → Price.
    Tracks sentiment "velocity" across the graph to predict the front-running window.
    """

    PLATFORM_WEIGHTS = {"reddit": 0.3, "twitter": 0.5, "bloomberg": 0.9, "sec": 1.0}
    PROPAGATION_LAG_HOURS = {"reddit": 0, "twitter": 1, "bloomberg": 3, "sec": 0}

    def __init__(self):
        self._nodes: Dict[str, List[Tuple[float, float]]] = {}  # platform -> [(score, timestamp)]

    def ingest(self, platform: str, sentiment_score: float, timestamp: float) -> None:
        if platform not in self._nodes:
            self._nodes[platform] = []
        self._nodes[platform].append((sentiment_score, timestamp))

    def propagated_score(self, target_lag_hours: float = 6.0) -> float:
        total_weight, weighted_sum = 0.0, 0.0
        for platform, readings in self._nodes.items():
            if not readings:
                continue
            lag = self.PROPAGATION_LAG_HOURS.get(platform, 0)
            weight = self.PLATFORM_WEIGHTS.get(platform, 0.5)
            if lag <= target_lag_hours:
                score = readings[-1][0]
                weighted_sum += score * weight
                total_weight += weight
        return weighted_sum / total_weight if total_weight > 0 else 0.0

    def breakout_probability(self) -> float:
        import math

        score = self.propagated_score()
        return 1.0 / (1.0 + math.exp(-score * 5))
