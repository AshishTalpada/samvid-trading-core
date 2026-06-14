import logging
from typing import Any

logger = logging.getLogger(__name__)


class FormalVerifier:
    """
    Formal logic verifier for agent reasoning paths.
    Applies Kolmogorov complexity heuristic: simpler proofs are trusted more.
    Rejects circular reasoning loops and over-parameterised justifications.
    """

    MAX_COMPLEXITY_SCORE = 50

    def complexity_score(self, reasoning_chain: list[str]) -> int:
        total = sum(len(step.split()) for step in reasoning_chain)
        unique = len(set(" ".join(reasoning_chain).lower().split()))
        return total - unique  # Penalise redundancy

    def verify(self, hypothesis: str, evidence: list[str]) -> dict[str, Any]:
        score = self.complexity_score(evidence)
        contradiction = any(
            bool(e1.split()) and e1.split()[0] == "NOT" and e1[4:] == e2
            for i, e1 in enumerate(evidence)
            for e2 in evidence[i + 1 :]
        )
        passed = score <= self.MAX_COMPLEXITY_SCORE and not contradiction
        logger.info(
            f"[VERIFIER] Hypothesis: '{hypothesis[:40]}' | Score: {score} | Passed: {passed}"
        )
        return {"passed": passed, "complexity_score": score, "contradiction_found": contradiction}
