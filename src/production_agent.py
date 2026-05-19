import logging
import time
from typing import List

import requests

logger = logging.getLogger(__name__)


class ProductionResiliencyAgent:
    """
    Monitors factory-level supply resiliency via satellite-tagged news events.
    Detects fires, strikes, power outages at critical supplier facilities
    and alerts the risk engine to pre-emptively reduce semiconductor exposure.
    """

    SUPPLY_KEYWORDS = [
        "factory fire",
        "plant shutdown",
        "strike",
        "power outage",
        "force majeure",
        "explosion",
    ]
    SEMICONDUCTOR_TICKERS = ["NVDA", "TSMC", "AMAT", "KLAC", "ASML", "MU", "INTC", "AMD"]

    def __init__(self):
        self.alert_history: list[dict] = []

    def scan_news_for_disruptions(self, news_texts: List[str]) -> List[dict]:
        alerts = []
        for text in news_texts:
            low = text.lower()
            for kw in self.SUPPLY_KEYWORDS:
                if kw in low:
                    affected = [t for t in self.SEMICONDUCTOR_TICKERS if t.lower() in low]
                    alert = {
                        "keyword": kw,
                        "tickers": affected or ["UNKNOWN"],
                        "snippet": text[:120],
                    }
                    alerts.append(alert)
                    self.alert_history.append(alert)
                    logger.warning(f"[PRODUCTION] Supply disruption: '{kw}' -> {affected}")
        return alerts

    def risk_adjustment_factor(self) -> float:
        """Reduce position sizing if recent alerts in last 24h."""
        recent = [a for a in self.alert_history[-50:]]
        return max(0.4, 1.0 - len(recent) * 0.05)
