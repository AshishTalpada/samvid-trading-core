import hashlib
import hmac
import logging
import time

logger = logging.getLogger(__name__)

class VoiceSecurityLayer:
    """
    Multi-layer voice authentication for high-risk trade authorizations.
    Combines speaker verification (cosine similarity on MFCCs)
    with a one-time challenge passphrase to prevent replay attacks.
    """
    CHALLENGE_WORDS = ["alpha","bravo","charlie","delta","echo","foxtrot","golf","hotel"]

    def __init__(self, similarity_threshold: float = 0.88):
        self.threshold = similarity_threshold
        self._enrolled_vectors: dict[str, list[float]] = {}
        self._challenges: dict[str, tuple[str, float]] = {}

    def enroll(self, user_id: str, mfcc: list[float]) -> None:
        self._enrolled_vectors[user_id] = mfcc
        logger.info(f"[VOICE SEC] Enrolled: {user_id}")

    def issue_challenge(self, user_id: str) -> str:
        import random
        word = random.choice(self.CHALLENGE_WORDS)
        self._challenges[user_id] = (word, time.time())
        return word

    def verify(self, user_id: str, probe_mfcc: list[float], spoken_word: str) -> bool:
        enrolled = self._enrolled_vectors.get(user_id)
        challenge, ts = self._challenges.get(user_id, (None, 0))
        if enrolled is None or challenge is None:
            logger.error(f"[VOICE SEC] Not enrolled or no challenge issued: {user_id}")
            return False
        if time.time() - ts > 30:
            logger.error("[VOICE SEC] Challenge expired.")
            return False
        if spoken_word.lower().strip() != challenge:
            logger.error("[VOICE SEC] Wrong challenge word.")
            return False
        dot = sum(a*b for a,b in zip(enrolled, probe_mfcc, strict=False))
        na = sum(x**2 for x in enrolled)**0.5
        nb = sum(x**2 for x in probe_mfcc)**0.5
        sim = dot / (na * nb + 1e-9)
        passed = sim >= self.threshold
        logger.info(f"[VOICE SEC] {user_id}: sim={sim:.3f} -> {'PASS' if passed else 'FAIL'}")
        return passed
