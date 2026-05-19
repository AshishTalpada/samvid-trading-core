import logging
import math
from typing import Dict, List

logger = logging.getLogger(__name__)


class CognitiveDiversityEnforcer:
    """
    Enforces diversity across the agent quorum to prevent groupthink.
    Monitors the Herfindahl-Hirschman Index (HHI) of vote distribution.
    High HHI = excessive consensus = herding risk.
    Blocks votes that would push HHI > 0.8.
    """

    MAX_HHI = 0.80

    def compute_hhi(self, votes: Dict[str, int]) -> float:
        total = sum(votes.values())
        if total == 0:
            return 0.0
        return sum((v / total) ** 2 for v in votes.values())

    def enforce(self, current_votes: Dict[str, int], new_vote: str) -> bool:
        trial = {**current_votes}
        trial[new_vote] = trial.get(new_vote, 0) + 1
        hhi = self.compute_hhi(trial)
        if hhi > self.MAX_HHI:
            logger.warning(
                f"[DIVERSITY] Vote '{new_vote}' blocked — HHI={hhi:.2f} exceeds max {self.MAX_HHI}."
            )
            return False
        return True

    def diversity_report(self, votes: Dict[str, int]) -> Dict:
        hhi = self.compute_hhi(votes)
        entropy = -sum(
            (v / max(sum(votes.values()), 1)) * math.log(v / max(sum(votes.values()), 1) + 1e-9)
            for v in votes.values()
        )
        return {
            "hhi": round(hhi, 4),
            "entropy": round(entropy, 4),
            "is_diverse": hhi <= self.MAX_HHI,
            "votes": votes,
        }
