import logging
from typing import Any

logger = logging.getLogger(__name__)

class ContrarianAgent:
    """
    Tracks extreme retail or 'talking head' sentiment to profit from crowd errors.
    """
    def __init__(self):
        self.crowd_sentiment_score = 0.0 # -1.0 to 1.0

    def evaluate_crowd_error(self, retail_long_ratio: float, retail_short_ratio: float,
                             influencer_bull_mentions: int, influencer_bear_mentions: int) -> dict[str, Any]:
        """
        Evaluate if the crowd is leaning too heavily in one direction.
        
        Args:
            retail_long_ratio: Percentage of retail traders long (0.0 to 1.0)
            retail_short_ratio: Percentage of retail traders short (0.0 to 1.0)
            influencer_bull_mentions: Raw count of bullish mentions by mainstream media/influencers
            influencer_bear_mentions: Raw count of bearish mentions
            
        Returns:
            Dictionary with contrarian signal.
        """
        # Calculate Retail Imbalance
        retail_imbalance = retail_long_ratio - retail_short_ratio

        # Calculate Influencer Imbalance
        total_influencer = influencer_bull_mentions + influencer_bear_mentions
        if total_influencer == 0:
            influencer_imbalance = 0.0
        else:
            influencer_imbalance = (influencer_bull_mentions - influencer_bear_mentions) / total_influencer

        # Composite Crowd Score (Weighted 60% Retail, 40% Influencer)
        self.crowd_sentiment_score = (0.6 * retail_imbalance) + (0.4 * influencer_imbalance)

        signal = "NEUTRAL"
        confidence = 0.0

        if self.crowd_sentiment_score > 0.75:
            # Extreme bullishness -> Sell signal
            signal = "SELL"
            confidence = min(1.0, self.crowd_sentiment_score)
            logger.warning("Contrarian Agent: Extreme crowd euphoria detected. Generating SELL signal.")
        elif self.crowd_sentiment_score < -0.75:
            # Extreme bearishness -> Buy signal
            signal = "BUY"
            confidence = min(1.0, abs(self.crowd_sentiment_score))
            logger.warning("Contrarian Agent: Extreme crowd panic detected. Generating BUY signal.")

        return {
            "crowd_score": self.crowd_sentiment_score,
            "signal": signal,
            "confidence": confidence
        }
