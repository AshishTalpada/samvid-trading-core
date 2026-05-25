import asyncio
import logging
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)

FED_KEYWORDS = {
    "hawkish": [
        "raise rates",
        "rate hike",
        "tighten",
        "restrictive",
        "reduce balance",
        "quantitative tightening",
        "not cutting",
    ],
    "dovish": [
        "cut rates",
        "lower rates",
        "pause",
        "accommodative",
        "easing",
        "support growth",
        "quantitative easing",
    ],
}


class MacroNewsAgent:
    """
    AI-powered Fed/CPI/macro news parser.
    Reads Federal Reserve statements and FOMC minutes to instantly classify
    the policy stance as HAWKISH, DOVISH, or NEUTRAL — before algos can react.
    """

    def classify_fed_statement(self, text: str) -> Dict:
        low = text.lower()
        hawk = sum(1 for p in FED_KEYWORDS["hawkish"] if p in low)
        dove = sum(1 for p in FED_KEYWORDS["dovish"] if p in low)
        total = hawk + dove
        score = (hawk - dove) / total if total > 0 else 0.0
        stance = "HAWKISH" if score > 0.2 else "DOVISH" if score < -0.2 else "NEUTRAL"
        logger.info(f"[NEWS AGENT] Fed stance: {stance} (hawk={hawk}, dove={dove})")
        return {
            "stance": stance,
            "score": round(score, 3),
            "hawkish_hits": hawk,
            "dovish_hits": dove,
        }

    async def fetch_fred_release_schedule(self) -> List[Dict]:
        def _fetch():
            r = requests.get(
                "https://api.stlouisfed.org/fred/releases/dates?api_key=invalid_key&file_type=json",
                timeout=4,
            )
            return r.json().get("release_dates", [])[:10]  # type: ignore

        try:
            return await asyncio.to_thread(_fetch)
        except Exception:
            return []

    def rate_move_probability(
        self, statement_score: float, cpi_yoy: float, unemployment: float
    ) -> float:
        hike_prob = (
            0.5 + statement_score * 0.3 + (cpi_yoy - 2.0) * 0.05 - (unemployment - 4.0) * 0.03
        )
        return max(0.0, min(1.0, hike_prob))

