import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

EXPERT_KEYWORDS = {
    "MACRO":   ["fed", "cpi", "gdp", "yield", "inflation"],
    "NEWS":    ["earnings", "merger", "acquisition", "lawsuit", "recall"],
    "PATTERN": ["breakout", "support", "resistance", "trend", "momentum"],
}

class MoEController:
    """Routes analysis to the appropriate expert model based on context keywords."""
    def route(self, context: str) -> str:
        ctx_lower = context.lower()
        scores: Dict[str, int] = {}
        for expert, keywords in EXPERT_KEYWORDS.items():
            scores[expert] = sum(1 for kw in keywords if kw in ctx_lower)
        winner = max(scores, key=lambda k: scores[k])
        if scores[winner] == 0:
            winner = "PATTERN"
        logger.debug(f"MoE routing to expert: {winner}")
        return winner
