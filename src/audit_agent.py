import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

BIAS_PATTERNS = {
    "FOMO": lambda votes: votes.count("BUY") > len(votes) * 0.85,
    "FEAR": lambda votes: votes.count("SELL") > len(votes) * 0.85,
    "ANCHORING": lambda votes: len(set(votes)) == 1,
}

class AuditAgent:
    """Audits quorum votes for cognitive bias patterns."""
    def audit(self, agent_votes: Dict[str, str]) -> Dict[str, bool]:
        votes = list(agent_votes.values())
        detected = {}
        for bias, check in BIAS_PATTERNS.items():
            if check(votes):
                logger.warning(f"Cognitive bias detected: {bias}")
                detected[bias] = True
        return detected
