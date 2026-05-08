import logging
logger = logging.getLogger(__name__)

class PromptOptimizer:
    """Iteratively refines agent prompts by evaluating output quality scores."""
    def __init__(self):
        self.prompt_scores: dict[str, list[float]] = {}

    def record_outcome(self, prompt_key: str, quality_score: float) -> None:
        self.prompt_scores.setdefault(prompt_key, []).append(quality_score)

    def best_prompt(self, candidates: list[str]) -> str:
        best = candidates[0]
        best_avg = -1.0
        for key in candidates:
            scores = self.prompt_scores.get(key, [])
            if scores:
                avg = sum(scores) / len(scores)
                if avg > best_avg:
                    best_avg = avg
                    best = key
        return best
