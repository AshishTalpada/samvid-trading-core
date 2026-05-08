import numpy as np
import logging
logger = logging.getLogger(__name__)

class CrashGAN:
    """Generates synthetic crash scenarios by amplifying historical drawdowns."""
    def __init__(self, amplification: float = 1.5):
        self.amplification = amplification

    def generate_crash(self, historical_returns: list[float], n_scenarios: int = 100) -> list[list[float]]:
        arr = np.array(historical_returns)
        crash_returns = arr[arr < arr.mean() - arr.std()]
        scenarios = []
        for _ in range(n_scenarios):
            sample_idx = np.random.choice(len(crash_returns), size=min(20, len(crash_returns)), replace=True)
            scenario = list(crash_returns[sample_idx] * self.amplification)
            scenarios.append(scenario)
        logger.debug(f"Generated {len(scenarios)} synthetic crash scenarios.")
        return scenarios
