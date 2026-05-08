import logging
from typing import Dict
logger = logging.getLogger(__name__)

class SkepticAgent:
    """
    Devil's Advocate agent. Generates counterarguments to every bullish or bearish thesis.
    Lowers quorum conviction when it finds opposing evidence.
    """
    def __init__(self, conviction_penalty: float = 0.15):
        self.penalty = conviction_penalty

    def challenge(self, thesis: str, signal: str, evidence: Dict[str, float]) -> Dict[str, Any]:
        challenges = []
        adjusted_confidence = evidence.get("base_confidence", 0.7)

        if signal == "BUY":
            if evidence.get("vix", 0) > 25:
                challenges.append("High VIX suggests elevated market fear.")
                adjusted_confidence -= self.penalty
            if evidence.get("rsi", 50) > 70:
                challenges.append("RSI overbought territory.")
                adjusted_confidence -= self.penalty
        elif signal == "SELL":
            if evidence.get("rsi", 50) < 30:
                challenges.append("RSI oversold; possible mean-reversion bounce.")
                adjusted_confidence -= self.penalty

        return {
            "challenges": challenges,
            "adjusted_confidence": max(0.0, adjusted_confidence),
            "veto": adjusted_confidence < 0.4
        }

from typing import Any
