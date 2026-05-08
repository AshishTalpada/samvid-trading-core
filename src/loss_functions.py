import numpy as np

class AdaptiveLoss:
    def __init__(self, regime: str = "NORMAL"):
        self.regime = regime

    def calculate_loss(self, expected: np.ndarray, actual: np.ndarray) -> float:
        errors = actual - expected
        if self.regime == "BEAR":
            downside = errors[errors < 0]
            return float(np.sum(downside**2) if len(downside) > 0 else 0.0)
        return float(np.mean(errors**2))
