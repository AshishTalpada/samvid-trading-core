import logging
import re
from typing import Dict, List

logger = logging.getLogger(__name__)

LANG_PATTERNS = {
    "bullish_en": ["surge", "rally", "beat", "record", "strong", "buy", "upgrade"],
    "bearish_en": ["crash", "miss", "downgrade", "weak", "sell", "decline", "warning"],
    "bullish_zh": ["上涨", "突破", "利好", "强势", "牛市"],
    "bearish_zh": ["下跌", "利空", "熊市", "崩盘", "抛售"],
    "bullish_de": ["stieg", "rekord", "kaufen", "stark", "gewinn"],
    "bearish_de": ["fiel", "schwach", "verkaufen", "verlust", "krise"],
}


class MultiLingualSentimentEngine:
    """
    Real-time multi-language sentiment engine for global macro news.
    Processes English, Mandarin (Simplified), and German financial texts.
    Provides normalised sentiment scores for cross-asset positioning.
    """

    def detect_language(self, text: str) -> str:
        if re.search(r"[\u4e00-\u9fff]", text):
            return "zh"
        if re.search(r"\b(der|die|das|und|ist|für|von)\b", text, re.IGNORECASE):
            return "de"
        return "en"

    def score(self, text: str) -> float:
        lang = self.detect_language(text)
        bull_key = f"bullish_{lang}"
        bear_key = f"bearish_{lang}"
        bull = sum(1 for w in LANG_PATTERNS.get(bull_key, []) if w in text)
        bear = sum(1 for w in LANG_PATTERNS.get(bear_key, []) if w in text)
        total = bull + bear
        if total == 0:
            return 0.0
        return (bull - bear) / total

    def batch_score(self, texts: List[str]) -> Dict[str, float]:
        scores = [self.score(t) for t in texts]
        mean = sum(scores) / len(scores) if scores else 0.0
        return {
            "mean": round(mean, 4),
            "bullish_count": sum(1 for s in scores if s > 0),
            "bearish_count": sum(1 for s in scores if s < 0),
            "signal": "BULLISH" if mean > 0.2 else "BEARISH" if mean < -0.2 else "NEUTRAL",  # type: ignore
        }
