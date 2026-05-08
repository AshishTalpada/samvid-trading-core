import numpy as np
import logging
logger = logging.getLogger(__name__)

class DiscoveryEngine:
    """AI-generates and tests new composite indicators for alpha discovery."""
    def __init__(self):
        self.discovered: list[dict] = []

    def evaluate_indicator(self, name: str, values: list[float], returns: list[float]) -> float:
        if len(values) != len(returns) or len(values) < 10:
            return 0.0
        v = np.array(values)
        r = np.array(returns)
        corr = float(np.corrcoef(v, r)[0, 1])
        if not np.isnan(corr) and abs(corr) > 0.2:
            self.discovered.append({"name": name, "correlation": corr})
            logger.info(f"Discovered indicator: {name} | corr={corr:.3f}")
        return corr
