import logging
from typing import Any, Callable, Dict, List

import numpy as np

logger = logging.getLogger(__name__)

class MixtureOfExpertsController:
    """
    Routes inference tasks to specialized SLM experts (e.g. Macro, News, Technicals).
    A gating network dynamically weights the contribution of each expert
    based on the current market regime (e.g. News expert gets 90% weight on CPI day).
    """
    def __init__(self):
        self.experts: Dict[str, Callable] = {}
        self.gating_weights: Dict[str, float] = {}

    def register_expert(self, name: str, fn: Callable) -> None:
        self.experts[name] = fn
        self.gating_weights[name] = 1.0 / (len(self.experts) or 1)

    def set_gating_weights(self, weights: Dict[str, float]) -> None:
        total = sum(weights.values())
        if total > 0:
            self.gating_weights = {k: v / total for k, v in weights.items()}
            logger.info(f"[MOE] Updated gating weights: {self.gating_weights}")

    def evaluate(self, input_data: Any) -> float:
        if not self.experts:
            return 0.0

        final_score = 0.0
        for name, expert_fn in self.experts.items():
            weight = self.gating_weights.get(name, 0.0)
            expert_pred = expert_fn(input_data)
            final_score += float(expert_pred) * weight

        return final_score
