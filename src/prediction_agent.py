import logging
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

class PredictionMarketAgent:
    """
    Ingests Polymarket prediction market data to extract crowd probability
    estimates for macro events (Fed rate decisions, election outcomes, defaults).
    Prediction markets are typically more accurate than polls 30 days out.
    """
    POLYMARKET_API = "https://clob.polymarket.com/markets"

    def fetch_markets(self, keywords: List[str]) -> List[Dict]:
        try:
            r = requests.get(self.POLYMARKET_API, params={"next_cursor": "MA=="}, timeout=6)
            markets = r.json().get("data", [])
            filtered = [m for m in markets if any(kw.lower() in m.get("question","").lower() for kw in keywords)]
            return [{"question": m["question"], "yes_price": m.get("best_ask", 0.5)} for m in filtered[:5]]
        except Exception as e:
            logger.error(f"[PREDICTION] Polymarket fetch error: {e}")
            return []

    def macro_probability(self, event: str) -> float:
        markets = self.fetch_markets([event])
        if not markets: return 0.5
        return float(markets[0].get("yes_price", 0.5))

    def signal_from_probability(self, prob: float, threshold: float = 0.7) -> str:
        if prob >= threshold: return "HIGH_CONVICTION_YES"
        if prob <= (1 - threshold): return "HIGH_CONVICTION_NO"
        return "UNCERTAIN"
