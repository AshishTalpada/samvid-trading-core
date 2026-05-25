import logging
from typing import List

logger = logging.getLogger(__name__)


class PoliticalRiskAgent:
    """
    Analyses legislative and geopolitical risk via Congress.gov API and news parsing.
    Tracks bill progression in key sectors (pharma price controls, crypto regulation, tariffs).
    Assigns a 0-1 risk score per sector.
    """

    BILL_KEYWORDS = {
        "pharma": ["drug pricing", "Medicare negotiation", "pharmaceutical"],
        "crypto": ["digital asset", "cryptocurrency", "bitcoin regulation"],
        "energy": ["carbon tax", "oil tariff", "clean energy mandate"],
        "tech": ["antitrust", "section 230", "data privacy"],
    }

    def score_legislative_risk(self, news_texts: List[str], sector: str) -> float:
        keywords = self.BILL_KEYWORDS.get(sector, [])
        hits = sum(1 for text in news_texts for kw in keywords if kw.lower() in text.lower())
        score = min(1.0, hits / 5.0)
        logger.info(f"[POLITICAL] Sector={sector} legislative risk score={score:.2f}")
        return score

    def geopolitical_risk_multiplier(
        self, sanctions_active: bool, conflict_zones: List[str]
    ) -> float:
        base = 1.0
        if sanctions_active:
            base += 0.3
        base += len(conflict_zones) * 0.1
        return min(2.0, base)
