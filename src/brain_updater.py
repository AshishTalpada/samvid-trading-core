import logging

logger = logging.getLogger(__name__)


class MicroWeightUpdater:
    """
    Online learning engine that applies micro weight updates after every live fill.
    Uses a momentum-based SGD with exponential decay to update agent confidence
    weights without full retraining. Prevents catastrophic forgetting via EWC penalty.
    """

    def __init__(self, learning_rate: float = 1e-4, momentum: float = 0.9, ewc_lambda: float = 0.4):
        self.lr = learning_rate
        self.momentum = momentum
        self.ewc_lambda = ewc_lambda
        self._weights: dict[str, float] = {}
        self._velocity: dict[str, float] = {}
        self._fisher: dict[str, float] = {}

    def update(self, agent_id: str, prediction_error: float) -> float:
        w = self._weights.get(agent_id, 1.0)
        v = self._velocity.get(agent_id, 0.0)
        f = self._fisher.get(agent_id, 0.0)
        grad = prediction_error + self.ewc_lambda * f * (w - 1.0)
        v_new = self.momentum * v - self.lr * grad
        w_new = max(0.1, min(3.0, w + v_new))
        self._weights[agent_id] = w_new
        self._velocity[agent_id] = v_new
        self._fisher[agent_id] = 0.9 * f + 0.1 * (grad**2)
        logger.debug(f"[BRAIN UPDATER] {agent_id}: w={w:.3f} -> {w_new:.3f}")
        return w_new

    def get_weight(self, agent_id: str) -> float:
        return self._weights.get(agent_id, 1.0)
