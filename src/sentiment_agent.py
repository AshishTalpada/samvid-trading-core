import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Sentiment weights calibrated from cross-asset backtesting
ASSET_SENTIMENT_WEIGHTS: Dict[str, float] = {
    "crypto": 1.5,  # Crypto is hyper-sensitive to social sentiment
    "equities": 0.8,
    "forex": 0.5,
    "commodities": 0.6,
}

BULLISH_KEYWORDS = [
    "bullish",
    "breakout",
    "moon",
    "surge",
    "rally",
    "buy",
    "long",
    "ath",
    "strong",
    "accumulate",
    "undervalued",
    "beat",
    "record",
]

BEARISH_KEYWORDS = [
    "bearish",
    "crash",
    "sell",
    "short",
    "dump",
    "fear",
    "panic",
    "rug",
    "scam",
    "correction",
    "overvalued",
    "miss",
    "warning",
    "crisis",
]


def score_text(text: str, asset_class: str = "equities") -> float:
    """
    Returns a sentiment score from -1.0 (extreme fear) to +1.0 (extreme greed).
    Applies an asset-class-specific sensitivity multiplier.
    """
    text_lower = text.lower()
    bull_hits = sum(1 for kw in BULLISH_KEYWORDS if kw in text_lower)
    bear_hits = sum(1 for kw in BEARISH_KEYWORDS if kw in text_lower)

    total = bull_hits + bear_hits
    if total == 0:
        return 0.0

    raw_score = (bull_hits - bear_hits) / total
    weight = ASSET_SENTIMENT_WEIGHTS.get(asset_class, 1.0)
    return max(-1.0, min(1.0, raw_score * weight))


def aggregate_sentiment(texts: List[str], asset_class: str = "equities") -> Dict[str, float]:
    """
    Aggregates sentiment across a batch of text signals (tweets, headlines, etc.)
    Returns mean, std, and a bull/bear classification.
    """
    if not texts:
        return {"mean": 0.0, "std": 0.0, "signal": "NEUTRAL"}  # type: ignore

    scores = [score_text(t, asset_class) for t in texts]
    mean = sum(scores) / len(scores)
    variance = sum((s - mean) ** 2 for s in scores) / len(scores)
    std = variance**0.5

    if mean > 0.25:
        signal = "BULLISH"
    elif mean < -0.25:
        signal = "BEARISH"
    else:
        signal = "NEUTRAL"

    logger.info(f"[SENTIMENT] {asset_class}: mean={mean:.3f} std={std:.3f} -> {signal}")
    return {"mean": mean, "std": std, "signal": signal}
