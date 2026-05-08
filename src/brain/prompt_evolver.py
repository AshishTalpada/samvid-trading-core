import logging
import math

logger = logging.getLogger(__name__)

class PromptEvolver:
    """
    Self-referential prompt optimization engine.
    Tracks which prompt variants produced the highest-conviction correct calls
    and evolves the wording through a lightweight A/B mutation loop.
    """
    def __init__(self):
        self._variants: dict[str, list[float]] = {}

    def register_outcome(self, prompt_id: str, was_correct: bool, confidence: float) -> None:
        score = confidence if was_correct else -confidence * 0.5
        if prompt_id not in self._variants:
            self._variants[prompt_id] = []
        self._variants[prompt_id].append(score)

    def best_variant(self) -> str | None:
        if not self._variants: return None
        scores = {pid: sum(s)/len(s) for pid, s in self._variants.items() if s}
        best = max(scores, key=scores.get)
        logger.info(f"[PROMPT EVOLVER] Best variant: {best} score={scores[best]:.3f}")
        return best

    def mutate(self, prompt: str, vix: float) -> str:
        tone = "cautious" if vix > 25 else "aggressive" if vix < 15 else "balanced"
        return prompt.replace("{TONE}", tone)
