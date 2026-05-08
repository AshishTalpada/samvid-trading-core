import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class DebateEngine:
    """Forces agents to justify their votes before a quorum decision is made."""
    def __init__(self, required_confidence: float = 0.6):
        self.required_confidence = required_confidence

    def run_debate(self, agent_votes: Dict[str, str], agent_confidences: Dict[str, float]) -> str:
        """
        Weighs votes by confidence and identifies the winning position.
        Rejects the trade if no side clears the confidence threshold.
        """
        scores: Dict[str, float] = {}
        for agent, vote in agent_votes.items():
            conf = agent_confidences.get(agent, 0.5)
            scores[vote] = scores.get(vote, 0.0) + conf

        if not scores:
            return "HOLD"

        winner = max(scores, key=lambda k: scores[k])
        total = sum(scores.values())
        win_confidence = scores[winner] / total if total > 0 else 0

        if win_confidence < self.required_confidence:
            logger.info(f"Debate inconclusive. Top vote: {winner} at {win_confidence:.1%}")
            return "HOLD"

        logger.info(f"Debate resolved: {winner} with {win_confidence:.1%} consensus")
        return winner
