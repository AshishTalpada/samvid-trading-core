import logging
logger = logging.getLogger(__name__)

class ContagionSentinel:
    """Detects cross-asset contagion - e.g. crypto sell-off bleeding into tech."""
    def __init__(self, correlation_drop_threshold: float = 0.4):
        self.threshold = correlation_drop_threshold

    def detect_contagion(self, asset_a_returns: list[float], asset_b_returns: list[float],
                         baseline_correlation: float) -> bool:
        if len(asset_a_returns) < 5 or len(asset_b_returns) < 5:
            return False
        import numpy as np
        current_corr = float(np.corrcoef(asset_a_returns, asset_b_returns)[0, 1])
        drop = baseline_correlation - current_corr
        if drop > self.threshold:
            logger.warning(f"Contagion detected: correlation dropped by {drop:.2f}")
            return True
        return False
