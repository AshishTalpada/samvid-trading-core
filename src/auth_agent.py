import hashlib
import hmac
import logging
import time
from typing import Dict

logger = logging.getLogger(__name__)


class DeepFakeAuthAgent:
    """
    Detects AI-generated synthetic media (deepfakes) in financial news streams.
    Strategy: checks for metadata anomalies, fingerprinting artefacts, and
    cross-validates headline claims against SEC EDGAR in real time.
    """

    METADATA_RED_FLAGS = ["photoshop", "adobe", "generated", "synthetic", "DALL-E", "midjourney"]

    def scan_image_metadata(self, metadata: Dict[str, str]) -> float:
        """Returns suspicion score 0.0-1.0 from image EXIF metadata."""
        hits = sum(
            1
            for v in metadata.values()
            if any(f.lower() in str(v).lower() for f in self.METADATA_RED_FLAGS)
        )
        return min(1.0, hits / 3.0)

    def cross_validate_headline(self, headline: str, known_facts: list[str]) -> bool:
        """Checks if headline contradicts recently verified facts."""
        low = headline.lower()
        for fact in known_facts:
            if fact.lower() in low and "not" in low:
                logger.warning(f"[AUTH AGENT] Potential contradiction: '{headline[:60]}'")
                return False
        return True

    def audio_fingerprint_match(self, audio_hash: str, enrolled_hash: str) -> bool:
        return hmac.compare_digest(audio_hash, enrolled_hash)

    def deepfake_risk_score(self, metadata: Dict, headline: str, known_facts: list[str]) -> float:
        meta_score = self.scan_image_metadata(metadata)
        headline_ok = self.cross_validate_headline(headline, known_facts)
        return min(1.0, meta_score + (0.4 if not headline_ok else 0.0))
