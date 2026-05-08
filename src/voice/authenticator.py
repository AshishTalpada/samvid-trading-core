import hashlib
import logging
from typing import Optional

logger = logging.getLogger(__name__)

class VoicePrintAuthenticator:
    """
    Voice biometric authentication layer.
    Enrolls a speaker voiceprint (MFCC feature vector) and verifies identity
    via cosine similarity against stored embeddings.
    Blocks trade authorization if voice doesn't match enrolled profile.
    """
    SIMILARITY_THRESHOLD = 0.85

    def __init__(self):
        self._enrolled: dict[str, list[float]] = {}

    def enroll(self, user_id: str, mfcc_vector: list[float]) -> None:
        self._enrolled[user_id] = mfcc_vector
        logger.info(f"[VOICE AUTH] Enrolled voiceprint for user: {user_id}")

    def _cosine_similarity(self, a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b, strict=False))
        norm_a = sum(x**2 for x in a) ** 0.5
        norm_b = sum(x**2 for x in b) ** 0.5
        return dot / (norm_a * norm_b + 1e-9)

    def authenticate(self, user_id: str, probe_vector: list[float]) -> bool:
        enrolled = self._enrolled.get(user_id)
        if enrolled is None:
            logger.error(f"[VOICE AUTH] No voiceprint enrolled for: {user_id}")
            return False
        sim = self._cosine_similarity(enrolled, probe_vector)
        passed = sim >= self.SIMILARITY_THRESHOLD
        logger.info(f"[VOICE AUTH] {user_id}: similarity={sim:.3f} -> {'PASS' if passed else 'FAIL'}")
        return passed
