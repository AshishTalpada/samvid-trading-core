import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class EnsembleDistiller:
    """
    Cross-LLM wisdom distillation engine.
    Collects predictions from multiple model endpoints (Claude, GPT-4, local SLM)
    and distills them into a single high-confidence ensemble decision using
    weighted voting scaled by each model's historical accuracy.
    """

    def __init__(self):
        self._accuracy_history: Dict[str, List[bool]] = {}

    def record_outcome(self, model_id: str, was_correct: bool) -> None:
        if model_id not in self._accuracy_history:
            self._accuracy_history[model_id] = []
        self._accuracy_history[model_id].append(was_correct)
        if len(self._accuracy_history[model_id]) > 200:
            self._accuracy_history[model_id].pop(0)

    def model_weight(self, model_id: str) -> float:
        hist = self._accuracy_history.get(model_id, [])
        if not hist:
            return 1.0
        return sum(hist) / len(hist)

    def distill(self, model_outputs: List[Dict[str, Any]]) -> Dict[str, Any]:
        weighted_scores: Dict[str, float] = {}
        total_weight = 0.0

        for output in model_outputs:
            model_id = output.get("model", "unknown")
            vote = output.get("vote", "ABSTAIN")
            confidence = float(output.get("confidence", 0.5))
            weight = self.model_weight(model_id)

            if vote not in weighted_scores:
                weighted_scores[vote] = 0.0
            weighted_scores[vote] += confidence * weight
            total_weight += weight

        if not weighted_scores or total_weight == 0:
            return {"vote": "ABSTAIN", "confidence": 0.0, "source": "ensemble_fallback"}

        best_vote = max(weighted_scores, key=weighted_scores.get)  # type: ignore
        ensemble_confidence = weighted_scores[best_vote] / total_weight
        logger.info(f"[DISTILL] Ensemble vote: {best_vote} ({ensemble_confidence:.2%}) from {len(model_outputs)} models")
        return {"vote": best_vote, "confidence": round(ensemble_confidence, 4), "breakdown": weighted_scores}
