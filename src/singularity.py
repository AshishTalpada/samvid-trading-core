import logging
import math
from collections import deque
from typing import Deque

import numpy as np

logger = logging.getLogger(__name__)


class UniversalSingularity:
    """
    Infinite Alpha Engine: The point where Sovereign's Learning Rate exceeds Market Randomness.
    Dynamically adjusts the AI's learning rate and exploration parameters based on the
    measured Shannon Entropy (Information density) and Hurst Exponent (Trend vs Mean-reversion)
    of the underlying market stream.
    """

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.price_history: Deque[float] = deque(maxlen=window_size)
        self.return_history: Deque[float] = deque(maxlen=window_size)

        # State variables
        self.current_learning_rate = 0.001
        self.market_entropy = 1.0
        self.hurst_exponent = 0.5  # 0.5 = Random Walk
        self.singularity_achieved = False

    def ingest_price(self, price: float):
        if len(self.price_history) > 0:
            ret = math.log(price / self.price_history[-1])
            self.return_history.append(ret)
        self.price_history.append(price)

    def _calculate_shannon_entropy(self, bins: int = 20) -> float:
        if len(self.return_history) < self.window_size // 2:
            return 1.0

        data = np.array(self.return_history)
        hist, _ = np.histogram(data, bins=bins, density=True)
        # Convert density to probabilities
        probs = hist * (np.max(data) - np.min(data)) / bins
        probs = probs[probs > 0]  # Filter zeros

        entropy = -np.sum(probs * np.log2(probs))
        # Normalize between 0 and 1 (approximate)
        max_entropy = np.log2(bins)
        return entropy / max_entropy  # type: ignore

    def _calculate_hurst(self) -> float:
        """
        Rescaled Range (R/S) Analysis to estimate the Hurst Exponent.
        H < 0.5 : Mean reverting (Anti-persistent)
        H == 0.5: Random Walk (Brownian Motion)
        H > 0.5 : Trending (Persistent)
        """
        if len(self.price_history) < 100:
            return 0.5

        ts = np.array(self.price_history)
        lags = range(2, 20)

        # Calculate the array of variances of the lagged differences
        tau = [np.sqrt(np.std(np.subtract(ts[lag:], ts[:-lag]))) for lag in lags]

        # Use a linear fit to estimate the Hurst Exponent
        poly = np.polyfit(np.log(lags), np.log(tau), 1)

        # Return the Hurst exponent (slope of the log-log plot)
        return poly[0] * 2.0  # type: ignore

    def evaluate_state(self) -> dict:
        """
        Evaluates the current market topology and adjusts the core intelligence learning rate.
        """
        self.market_entropy = self._calculate_shannon_entropy()
        self.hurst = self._calculate_hurst()

        # If the market is highly random (Entropy ~ 1.0, Hurst ~ 0.5),
        # we DECREASE the learning rate to avoid overfitting to noise.
        # If the market has structural inefficiency (Low Entropy, Hurst > 0.6 or < 0.4),
        # we INCREASE the learning rate to aggressively capture the alpha.

        structural_inefficiency = abs(self.hurst - 0.5) * 2.0  # 0 to 1 scale
        clarity = 1.0 - self.market_entropy

        # Base LR modified by market clarity and structural trends
        target_lr = 0.0001 + (0.01 * structural_inefficiency * clarity)

        # Smooth transition
        self.current_learning_rate = (self.current_learning_rate * 0.9) + (target_lr * 0.1)

        # Singularity Condition: The system's predictive clarity exceeds the market's randomness
        if clarity > 0.8 and self.current_learning_rate > self.market_entropy:
            if not self.singularity_achieved:
                logger.critical(
                    f"UNIVERSAL SINGULARITY ACHIEVED. System learning rate ({self.current_learning_rate:.5f}) exceeds market entropy ({self.market_entropy:.5f})."
                )
            self.singularity_achieved = True
        else:
            self.singularity_achieved = False

        return {
            "entropy": self.market_entropy,
            "hurst": self.hurst,
            "learning_rate": self.current_learning_rate,
            "singularity": self.singularity_achieved,
        }
