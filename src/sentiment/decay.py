import logging
import math
from typing import List

logger = logging.getLogger(__name__)


class SentimentDecayModel:
    """
    Models the half-life of news sentiment impact on price.
    Earnings beat: ~72h half-life. Analyst upgrade: ~48h. Tweet: ~2h.
    Uses exponential decay: impact(t) = S0 * exp(-lambda * t)
    """

    HALF_LIVES = {
        "earnings": 72.0,
        "analyst_upgrade": 48.0,
        "macro_data": 24.0,
        "tweet": 2.0,
        "news_article": 8.0,
        "sec_filing": 120.0,
    }

    def decay(self, initial_sentiment: float, event_type: str, hours_elapsed: float) -> float:
        half_life = self.HALF_LIVES.get(event_type, 24.0)
        lam = math.log(2) / half_life
        decayed = initial_sentiment * math.exp(-lam * hours_elapsed)
        return round(decayed, 4)

    def aggregate_decayed_sentiment(self, events: List[dict], current_time_hours: float) -> float:
        total = 0.0
        for ev in events:
            age_hours = current_time_hours - ev.get("time_hours", 0)
            total += self.decay(ev.get("sentiment", 0.0), ev.get("type", "news_article"), age_hours)
        return max(-1.0, min(1.0, total))
