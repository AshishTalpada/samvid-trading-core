import logging
import time
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

class RDVelocityAgent:
    """
    Tracks patent filing velocity as a leading indicator for innovation breakout.
    Companies filing 3x+ more patents YoY often precede product cycle acceleration.
    Maps to equities via USPTO API proxy.
    """
    USPTO_API = "https://developer.uspto.gov/ibd-api/v1/patent/application"

    def estimate_velocity(self, ticker: str, patent_counts_by_quarter: List[int]) -> Dict:
        if len(patent_counts_by_quarter) < 2:
            return {"ticker": ticker, "velocity": 0.0, "signal": "INSUFFICIENT"}
        recent = sum(patent_counts_by_quarter[-2:])
        prior = sum(patent_counts_by_quarter[-4:-2]) or 1
        velocity = (recent - prior) / prior
        signal = "BREAKOUT" if velocity > 2.0 else "ACCELERATING" if velocity > 0.5 else "STABLE" if velocity > -0.2 else "DECLINING"
        logger.info(f"[R&D] {ticker}: velocity={velocity:.2f}x YoY -> {signal}")
        return {"ticker": ticker, "velocity": round(velocity, 3), "signal": signal}
