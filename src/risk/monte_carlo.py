import logging

import numpy as np

logger = logging.getLogger(__name__)


class MonteCarloRisk:
    """
    Runs fast vectorized Monte Carlo simulations to calculate Ruin Probability.
    """

    def __init__(self, simulations: int = 10000, horizon_steps: int = 100):
        self.simulations = max(1, int(simulations))
        self.horizon_steps = max(1, int(horizon_steps))

    def simulate_ruin_probability(
        self, returns: list[float], current_equity: float, ruin_level: float
    ) -> float:
        """
        Runs Monte Carlo simulations to find the probability of equity dropping below ruin_level.

        Args:
            returns: Historical returns for the asset/portfolio.
            current_equity: The starting equity value.
            ruin_level: The equity value that constitutes "ruin".

        Returns:
            Probability (0.0 to 1.0) of hitting ruin.
        """
        if current_equity <= 0:
            logger.warning("Invalid current equity for Monte Carlo simulation.")
            return 0.0
        if ruin_level <= 0:
            return 0.0
        if ruin_level >= current_equity:
            return 1.0
        if len(returns) < 10:
            logger.warning("Insufficient returns data for Monte Carlo simulation.")
            return 0.0

        ret_arr = np.array(returns, dtype=float)
        ret_arr = ret_arr[np.isfinite(ret_arr)]
        ret_arr = np.clip(ret_arr, -0.99, 10.0)
        if len(ret_arr) < 10:
            logger.warning("Insufficient finite returns data for Monte Carlo simulation.")
            return 0.0
        mu = np.mean(ret_arr)
        sigma = np.std(ret_arr)
        if not np.isfinite(mu) or not np.isfinite(sigma):
            return 0.0

        # Generate random returns for all simulations and steps
        random_returns = np.random.normal(mu, sigma, (self.simulations, self.horizon_steps))

        # Cumulative returns over the horizon
        cumulative_returns = np.cumprod(1 + random_returns, axis=1)

        # Equity paths
        equity_paths = current_equity * cumulative_returns

        # Find paths that hit the ruin level
        ruin_hits = np.any(equity_paths <= ruin_level, axis=1)

        ruin_probability = np.sum(ruin_hits) / self.simulations
        return float(ruin_probability)
