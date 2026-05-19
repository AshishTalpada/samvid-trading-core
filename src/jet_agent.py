import logging
import time
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class CorporateJetTracker:
    """
    Tracks corporate jet AIS/ADS-B signals to airports near M&A deal-making cities.
    Historically: CEO private jets at Omaha/Sun Valley 2-3 days before public M&A announcement.
    """

    MA_AIRPORTS = {
        "KBFF": "Scottsbluff (Berkshire Hathaway)",
        "KSUN": "Sun Valley (Allen & Co)",
        "KLUK": "Cincinnati (P&G HQ)",
        "KHPN": "Westchester (NYC deal meetings)",
    }

    def score_activity(self, flight_logs: List[Dict]) -> Dict[str, float]:
        """
        Returns a dict of {airport_code: activity_score} where score 0-1
        represents unusual jet clustering relative to 30-day baseline.
        """
        from collections import Counter

        airport_counts: Counter = Counter()
        for log in flight_logs:
            dest = log.get("destination", "")
            if dest in self.MA_AIRPORTS:
                airport_counts[dest] += 1
        total = sum(airport_counts.values()) or 1
        return {k: min(1.0, v / 10.0) for k, v in airport_counts.items()}

    def ma_probability(self, scores: Dict[str, float]) -> float:
        return min(1.0, sum(scores.values()) / len(self.MA_AIRPORTS))
