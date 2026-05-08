import logging

import numpy as np

logger = logging.getLogger(__name__)

class AntiFragilityEngine:
    """
    Identifies if an asset exhibits anti-fragile properties 
    (gains disproportionately from volatility/chaos).
    """
    def __init__(self, lookback_window: int = 20):
        self.lookback_window = lookback_window

    def calculate_fragility_score(self, asset_returns: list[float],
                                  market_volatility: list[float]) -> float:
        """
        Measures the correlation between asset returns and market volatility spikes.
        
        Args:
            asset_returns: List of asset percentage returns.
            market_volatility: List of market volatility metrics (e.g., VIX changes).
            
        Returns:
            Anti-fragility score (-1.0 to 1.0). 
            > 0.5 means highly anti-fragile.
            < -0.5 means highly fragile.
        """
        if len(asset_returns) < self.lookback_window or len(market_volatility) < self.lookback_window:
            return 0.0

        returns = np.array(asset_returns[-self.lookback_window:])
        volatility = np.array(market_volatility[-self.lookback_window:])

        # Calculate correlation between returns and volatility
        correlation_matrix = np.corrcoef(returns, volatility)

        if np.isnan(correlation_matrix[0, 1]):
            return 0.0

        score = correlation_matrix[0, 1]

        # Adjust score by the magnitude of positive outlier returns
        # Anti-fragile assets should have positive fat tails
        positive_tails = returns[returns > np.mean(returns) + np.std(returns)]
        if len(positive_tails) > 0:
            tail_multiplier = 1.0 + min(0.5, np.mean(positive_tails) * 10)
            score *= tail_multiplier

        return float(np.clip(score, -1.0, 1.0))
