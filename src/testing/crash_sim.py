import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)

class BlackSwanCrashSimulator:
    """
    GAN-inspired crash generator for stress testing.
    Generates 2008-style and 2020-style crash scenarios using
    Geometric Brownian Motion with fat-tailed (Student-t) shocks.
    """
    def __init__(self, seed: int = 42):
        self.rng = np.random.default_rng(seed)

    def generate_crash_path(self, days: int = 30, severity: str = "moderate", start_price: float = 100.0) -> List[float]:
        severity_params = {
            "mild":     {"vol": 0.03, "drift": -0.01, "df": 5},
            "moderate": {"vol": 0.06, "drift": -0.03, "df": 3},
            "severe":   {"vol": 0.12, "drift": -0.08, "df": 2},
            "2008":     {"vol": 0.15, "drift": -0.10, "df": 2},
        }
        p = severity_params.get(severity, severity_params["moderate"])
        shocks = self.rng.standard_t(df=p["df"], size=days) * p["vol"] + p["drift"]
        prices = [start_price]
        for s in shocks:
            prices.append(prices[-1] * (1 + s))
        logger.info(f"[CRASH SIM] {severity} scenario: {start_price:.0f} -> {prices[-1]:.0f} ({(prices[-1]/start_price-1)*100:.1f}%)")
        return prices

    def run_stress_suite(self, start_price: float = 100.0) -> dict[str, List[float]]:
        return {sev: self.generate_crash_path(severity=sev, start_price=start_price)
                for sev in ["mild", "moderate", "severe", "2008"]}
