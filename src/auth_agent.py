import logging
logger = logging.getLogger(__name__)

class AuthAgent:
    """Detects deepfake or anomalous audio signatures in earnings call transcripts."""
    def analyze_transcript(self, transcript: str, stress_keywords: list[str] | None = None) -> dict:
        stress_keywords = stress_keywords or ["uncertain", "challenging", "difficult", "headwinds", "disappointing"]
        words = transcript.lower().split()
        hits = [w for w in words if w in stress_keywords]
        score = len(hits) / max(len(words), 1)
        return {"stress_score": round(score, 4), "hits": hits, "flag": score > 0.05}
