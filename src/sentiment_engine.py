import logging

logger = logging.getLogger(__name__)

class SentimentEngine:
    """Multi-language sentiment aggregation from financial news feeds."""
    POSITIVE_WORDS = {"bullish", "growth", "beat", "surge", "profit", "strong"}
    NEGATIVE_WORDS = {"bearish", "loss", "miss", "decline", "weak", "cut", "fall"}

    def score(self, text: str) -> float:
        words = set(text.lower().split())
        pos = len(words & self.POSITIVE_WORDS)
        neg = len(words & self.NEGATIVE_WORDS)
        total = pos + neg
        if total == 0:
            return 0.0
        return (pos - neg) / total
