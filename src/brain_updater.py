import logging
logger = logging.getLogger(__name__)

class MicroWeightUpdater:
    def __init__(self, learning_rate: float = 1e-5):
        self.learning_rate = learning_rate

    def apply_update(self, current_weights: list[float], gradient: list[float]) -> list[float]:
        logger.debug("Applying micro-weight updates post-fill.")
        return [w - self.learning_rate * g for w, g in zip(current_weights, gradient)]
