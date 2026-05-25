import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class FootfallAnalysisAgent:
    """
    Analyzes satellite/CCTV derived parking lot density data to estimate
    retail foot traffic for big-box retailers (WMT, TGT, HD) before earnings.
    """

    def __init__(self, base_density: float = 0.5):
        self.base_density = base_density
        self.history: List[float] = []

    def ingest_density(self, density: float) -> None:
        self.history.append(density)
        if len(self.history) > 30:
            self.history.pop(0)

    def estimate_traffic_trend(self) -> float:
        if len(self.history) < 7:
            return 0.0

        recent_avg = float(np.mean(self.history[-7:]))
        past_avg = float(np.mean(self.history[:-7])) if len(self.history) > 7 else self.base_density

        # Percentage change in foot traffic
        trend = (recent_avg - past_avg) / (past_avg + 1e-9)

        logger.info(f"[RETAIL AGENT] 7-day foot traffic trend: {trend:+.2%}")
        return float(trend)
