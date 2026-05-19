import logging
from typing import Any, Dict

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
            "veto": adjusted_confidence < 0.4,
        }

    def run_adversarial_debate(
        self, proposal: Dict[str, Any], opponents: list[str]
    ) -> Dict[str, Any]:
        """
        Forces the proposing agents to defend their thesis against the Skeptic's counter-points.
        """
        logger.info(f"Skeptic: Initiating ADVERSARIAL DEBATE against {opponents}")

        signal = proposal.get("vote", "HOLD")
        reasons = proposal.get("reason", "No reason provided.")

        # Challenge the core logic
        counter_thesis = f"Countering {signal}: "
        if signal == "BUY":
            counter_thesis += "Market depth is thinning and macro-tailwinds are over-extended."
        elif signal == "SELL":
            counter_thesis += "Local support levels are firm and liquidity sweeps are likely."
        else:
            counter_thesis += "Indecision is the greatest risk in high-freq windows."

        logger.info(f"Skeptic Thesis: {counter_thesis}")

        # The debate outcome is a refined confidence score
        is_weak = len(reasons) < 20 or "momentum" in reasons.lower()
        refined_conf = proposal.get("confidence", 0.5) * (0.75 if is_weak else 1.1)

        return {
            "agent": "Agent_H_Skeptic",
            "vote": "NO" if refined_conf < 0.6 else "YES",
            "confidence": refined_conf,
            "counter_thesis": counter_thesis,
            "debate_resolved": True,
        }
