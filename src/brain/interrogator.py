import logging
from typing import Any

logger = logging.getLogger(__name__)


class SovereignInterrogator:
    """
    Natural language interrogation engine for quorum decisions.
    Allows the operator to ask: "Sovereign, why did you reject DIA?"
    and receive a structured, evidence-based justification.
    """

    def interrogate(self, decision: dict[str, Any], question: str) -> str:
        decision_type = decision.get("decision", "UNKNOWN")
        confidence = decision.get("confidence", 0.0)
        reason = decision.get("reason", "No reason recorded.")
        votes = decision.get("votes") or []
        if not isinstance(votes, list):
            votes = []
        yes_agents = [v["agent"] for v in votes if isinstance(v, dict) and v.get("vote") == "YES"]
        no_agents = [v["agent"] for v in votes if isinstance(v, dict) and v.get("vote") == "NO"]
        abstain_agents = [v["agent"] for v in votes if isinstance(v, dict) and v.get("vote") == "ABSTAIN"]
        response = (
            f"Decision: {decision_type} (Confidence: {confidence:.0%})\n"
            f"Reason: {reason}\n"
            f"YES votes ({len(yes_agents)}): {', '.join(yes_agents) or 'None'}\n"
            f"NO votes ({len(no_agents)}): {', '.join(no_agents) or 'None'}\n"
            f"ABSTAIN ({len(abstain_agents)}): {', '.join(abstain_agents) or 'None'}"
        )
        logger.info(f"[INTERROGATOR] Q: '{question}' -> {decision_type}")
        return response
