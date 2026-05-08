import logging
import re
import time

import requests

logger = logging.getLogger(__name__)

CYBERSECURITY_FEEDS = [
    "https://feeds.feedburner.com/TheHackersNews",
    "https://www.bleepingcomputer.com/feed/",
]

THREAT_TICKERS: dict[str, list[str]] = {
    "MSFT": ["microsoft", "azure", "windows"],
    "AMZN": ["amazon", "aws", "s3"],
    "GOOG": ["google", "chrome", "android"],
    "TSLA": ["tesla", "autopilot", "canbus"],
}

class CyberRiskAgent:
    """
    Monitors cybersecurity news feeds and maps breach reports to affected tickers.
    A major breach can cause -5% to -25% moves before official disclosure.
    """
    def scan_feeds(self, ticker: str) -> dict:
        keywords = THREAT_TICKERS.get(ticker.upper(), [ticker.lower()])
        hits = []
        for url in CYBERSECURITY_FEEDS:
            try:
                r = requests.get(url, timeout=4)
                for kw in keywords:
                    count = r.text.lower().count(kw)
                    if count > 0:
                        hits.append({"feed": url, "keyword": kw, "mentions": count})
            except Exception as e:
                logger.warning(f"[CYBER] Feed error {url}: {e}")
        risk_score = min(1.0, sum(h["mentions"] for h in hits) / 10.0)
        return {"ticker": ticker, "risk_score": risk_score, "hits": hits}
