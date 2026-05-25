import logging
from typing import Dict

import numpy as np

logger = logging.getLogger(__name__)


class LogisticsChainSimulator:
    """
    Monte Carlo supply chain disruption simulator.
    Models how hurricanes, droughts, and port strikes ripple through commodity pricing.
    Runs 1,000 paths to compute expected price impact distribution.
    """

    def __init__(self, n_simulations: int = 1000, rng_seed: int = 42):
        self.n = n_simulations
        self.rng = np.random.default_rng(rng_seed)

    def simulate_disruption(
        self, base_price: float, disruption_severity: float, duration_days: int
    ) -> Dict:
        paths = []
        for _ in range(self.n):
            price = base_price
            for d in range(duration_days):
                shock = self.rng.normal(disruption_severity * 0.02, 0.015)
                price *= 1 + shock
            paths.append(price)
        arr = np.array(paths)
        return {
            "expected_price": float(np.mean(arr)),
            "p5_price": float(np.percentile(arr, 5)),
            "p95_price": float(np.percentile(arr, 95)),
            "expected_pct_change": float((np.mean(arr) / base_price - 1) * 100),
            "var_95": float(np.percentile(arr - base_price, 5)),
        }
