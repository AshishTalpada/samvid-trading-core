import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


class SelfReferentialReasoningEngine:
    """
    Applies Gödel's Incompleteness / Hofstadter Strange Loop reasoning.
    The system evaluates its own reasoning process to detect when it is
    "stuck in a loop" — making the same wrong trade repeatedly.
    Triggers meta-cognitive reset when self-similarity score exceeds 0.9.
    """

    def __init__(self, loop_threshold: float = 0.90, lookback: int = 10):
        self.threshold = loop_threshold
        self.lookback = lookback
        self._decision_history: list[str] = []

    def record_decision(self, decision: str) -> None:
        self._decision_history.append(decision)
        if len(self._decision_history) > 100:
            self._decision_history.pop(0)

    def self_similarity_score(self) -> float:
        recent = self._decision_history[-self.lookback :]
        if not recent:
            return 0.0
        dominant = max(set(recent), key=recent.count)
        return recent.count(dominant) / len(recent)

    def is_loop_detected(self) -> bool:
        score = self.self_similarity_score()
        if score >= self.threshold:
            logger.critical(
                f"[SELF-REF] Reasoning loop detected! Self-similarity={score:.2f}. Triggering reset."
            )
            return True
        return False

    def metacognitive_reset(self) -> Dict[str, Any]:
        logger.info("[SELF-REF] Executing metacognitive reset — clearing decision history.")
        cleared = len(self._decision_history)
        self._decision_history.clear()
        return {"cleared_decisions": cleared, "action": "RESET_COMPLETE"}
