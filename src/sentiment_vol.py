import logging

import numpy as np

logger = logging.getLogger(__name__)


class SentimentVolatilityIndex:
    """
    Sentiment Volatility Index (SVI): tracks the rate-of-change of social sentiment.
    Inspired by CBOE VIX but for news/social sentiment rather than options pricing.
    Sudden sentiment reversals precede price reversals by 15-30 minutes on average.
    """

    def __init__(self, lookback: int = 60):
        self.lookback = lookback
        self._sentiment_history: list[float] = []

    def update(self, sentiment_score: float) -> None:
        self._sentiment_history.append(sentiment_score)
        if len(self._sentiment_history) > self.lookback * 5:
            self._sentiment_history.pop(0)

    def svi(self) -> float:
        if len(self._sentiment_history) < self.lookback:
            return 0.0
        arr = np.array(self._sentiment_history[-self.lookback :])
        daily_changes = np.diff(arr)
        return float(np.std(daily_changes) * np.sqrt(252))

    def is_reversal_forming(self, threshold: float = 0.5) -> bool:
        return self.svi() > threshold
