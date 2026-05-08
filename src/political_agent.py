import logging
logger = logging.getLogger(__name__)

class PoliticalAgent:
    """Analyzes legislative language to predict regulatory impact on sectors."""
    BEARISH_TERMS = ["windfall tax", "price cap", "antitrust", "nationalize", "ban"]
    BULLISH_TERMS = ["deregulate", "subsidy", "tax credit", "infrastructure bill", "stimulus"]

    def analyze(self, legislation_text: str) -> dict[str, float]:
        text = legislation_text.lower()
        bear_hits = sum(1 for t in self.BEARISH_TERMS if t in text)
        bull_hits = sum(1 for t in self.BULLISH_TERMS if t in text)
        total = bear_hits + bull_hits or 1
        sentiment = (bull_hits - bear_hits) / total
        logger.info(f"Political sentiment: {sentiment:.2f} (bull={bull_hits}, bear={bear_hits})")
        return {"sentiment": sentiment, "bull_signals": bull_hits, "bear_signals": bear_hits}
