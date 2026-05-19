import logging
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class BayesianRegimeAgent:
    """
    Probabilistic modeling of BULL/BEAR/CHOP transitions using
    Bayesian Inference over recent returns and volatility.
    Outputs the probability distribution over all possible regimes.
    """

    def __init__(self):
        self.regimes = ["BULL", "BEAR", "CHOP"]
        self.prior = np.array([0.33, 0.33, 0.34])

    def update_beliefs(self, recent_returns: List[float], recent_vol: float) -> str:
        if not recent_returns:
            return "CHOP"

        avg_ret = float(np.mean(recent_returns))

        # Likelihoods given data (mocked Gaussian PDF evaluation)
        # Bull: positive returns, low vol. Bear: neg returns, high vol. Chop: zero returns, low vol.
        l_bull = np.exp(-((avg_ret - 0.001) ** 2) / (2 * 0.005**2)) / recent_vol
        l_bear = np.exp(-((avg_ret + 0.002) ** 2) / (2 * 0.010**2)) * recent_vol
        l_chop = np.exp(-((avg_ret - 0.0) ** 2) / (2 * 0.002**2)) / recent_vol

        likelihoods = np.array([l_bull, l_bear, l_chop]) + 1e-9

        # Bayes Rule: Posterior = Likelihood * Prior / Evidence
        posterior = likelihoods * self.prior
        posterior /= np.sum(posterior)

        self.prior = posterior  # Recursive update

        best_idx = int(np.argmax(posterior))
        detected = self.regimes[best_idx]
        logger.debug(f"[REGIME] Detected: {detected} (Prob: {posterior[best_idx]:.1%})")
        return detected
