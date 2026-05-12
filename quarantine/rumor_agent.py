import logging
import re
import time
from typing import Dict, List

logger = logging.getLogger(__name__)

class RumorArbitrageAgent:
    """
    Trades the gap between 'Rumor' and 'Official' news releases.
    Classic pattern: stock moves on rumor, gives back 30-50% after official confirmation.
    Detects unconfirmed rumor words in news flow and tags them for reversal plays.
    """
    RUMOR_WORDS = ["reportedly","sources say","rumored","unconfirmed","sources familiar",
                   "could announce","may announce","expected to","whisper","word is"]
    CONFIRMATION_WORDS = ["officially","confirmed","announces","press release","SEC filing","8-K"]

    def classify_news(self, headline: str) -> str:
        low = headline.lower()
        if any(w in low for w in self.RUMOR_WORDS): return "RUMOR"
        if any(w in low for w in self.CONFIRMATION_WORDS): return "CONFIRMED"
        return "NEUTRAL"

    def rumor_to_confirm_gap(self, rumors: List[Dict], confirmations: List[Dict]) -> List[Dict]:
        plays = []
        for r in rumors:
            for c in confirmations:
                if r.get("ticker") == c.get("ticker"):
                    gap_mins = (c.get("ts",0) - r.get("ts",0)) / 60
                    plays.append({"ticker": r["ticker"], "gap_minutes": round(gap_mins,1), "type": "RUMOR_TO_CONFIRM"})
        return plays
