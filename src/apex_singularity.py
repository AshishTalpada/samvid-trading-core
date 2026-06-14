import logging

import numpy as np

logger = logging.getLogger(__name__)


class SovereignSingularity:
    """
    The Sovereign Singularity: the theoretical inflection point where the system's
    learning rate exceeds the market's information production rate.
    Tracks the ratio of model improvement per trade vs. market entropy per bar.
    When ratio > 1.0, the system has achieved statistical supremacy.
    """

    def __init__(self):
        self._model_improvements: list[float] = []
        self._market_entropies: list[float] = []

    def record_improvement(self, delta_sharpe: float) -> None:
        self._model_improvements.append(abs(delta_sharpe))

    def record_market_entropy(self, returns: list[float]) -> None:
        arr = np.array(returns)
        counts, _ = np.histogram(arr, bins=20)
        total = counts.sum()
        if total == 0:
            return
        probs = counts[counts > 0] / total  # true probability mass, sums to 1
        entropy = float(-np.sum(probs * np.log(probs + 1e-9)))
        self._market_entropies.append(entropy)

    def singularity_ratio(self) -> float:
        if not self._model_improvements or not self._market_entropies:
            return 0.0
        learn_rate = sum(self._model_improvements[-20:]) / len(self._model_improvements[-20:])
        market_noise = sum(self._market_entropies[-20:]) / len(self._market_entropies[-20:])
        ratio = learn_rate / (market_noise + 1e-9)
        if ratio > 1.0:
            logger.critical(f"[SINGULARITY]  SINGULARITY THRESHOLD CROSSED! Ratio={ratio:.4f}")
        return round(ratio, 6)
