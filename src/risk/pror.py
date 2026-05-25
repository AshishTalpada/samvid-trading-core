import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class ProbabilityOfRuinCalculator:
    """
    Continuous PRoR (Probability of Ruin) calculation using Monte Carlo walk.
    Computes the mathematical likelihood of the portfolio dropping below a critical
    ruin threshold given the empirical distribution of recent trade returns.
    """

    def __init__(self, simulations: int = 10000, horizon_trades: int = 100):
        self.simulations = simulations
        self.horizon = horizon_trades

    def calculate_pror(
        self, recent_returns: List[float], starting_capital: float, ruin_level: float
    ) -> float:
        if len(recent_returns) < 20:
            return 0.0  # Not enough data

        mu = np.mean(recent_returns)
        sigma = np.std(recent_returns)

        if sigma == 0:
            return 1.0 if starting_capital + (mu * self.horizon) <= ruin_level else 0.0

        # Run Monte Carlo geometric random walks
        ruin_count = 0
        for _ in range(self.simulations):
            # Sample with replacement from empirical returns
            path_returns = np.random.choice(recent_returns, size=self.horizon, replace=True)
            capital = starting_capital
            for r in path_returns:
                capital *= 1 + r
                if capital <= ruin_level:
                    ruin_count += 1
                    break

        pror = ruin_count / self.simulations

        if pror > 0.05:
            logger.critical(f"[PRoR] FATAL RISK: Probability of Ruin is {pror:.2%} > 5% threshold!")

        return float(pror)
