import logging

import numpy as np

logger = logging.getLogger(__name__)

class TailRiskModel:
    """
    Models the 1% chance of catastrophic loss (Conditional Value at Risk).
    """
    def calculate_es(self, returns: list[float], confidence_level: float = 0.99) -> float:
        """
        Calculates the Expected Shortfall (CVaR) at the given confidence level.
        Returns the average loss of the worst (1 - confidence_level) cases.
        
        Args:
            returns: Historical returns of the portfolio or asset.
            confidence_level: Typically 0.99 for the 1% tail.
            
        Returns:
            Expected Shortfall as a negative float representing the average tail loss.
        """
        if not returns or len(returns) < 5:
            return 0.0

        ret_arr = np.array(returns)

        # Calculate Value at Risk (VaR)
        percentile = (1 - confidence_level) * 100
        var = np.percentile(ret_arr, percentile)

        # Expected Shortfall is the average of returns worse than VaR
        tail_losses = ret_arr[ret_arr <= var]

        if len(tail_losses) == 0:
            return 0.0

        return float(np.mean(tail_losses))
