import logging
from typing import List

logger = logging.getLogger(__name__)

class VocalJitterAuditor:
    """
    Audits earnings call audio feeds for micro-tremors (jitter) and unnatural
    pauses in the CEO's voice, indicating stress or deception regarding forward guidance.
    """
    def __init__(self, baseline_pause_ms: float = 300.0):
        self.baseline_pause = baseline_pause_ms

    def compute_pause_stats(self, pause_durations_ms: List[float]) -> float:
        if not pause_durations_ms:
            return 0.0

        import numpy as np
        avg_pause = float(np.mean(pause_durations_ms))
        deviation = avg_pause / self.baseline_pause

        if deviation > 1.5:
            logger.warning(f"[VOCAL AUDIT] Excessive unnatural pausing detected (Deviation: {deviation:.1f}x baseline). Deception likely.")

        return deviation

    def compute_speech_rate(self, word_count: int, audio_duration_sec: float) -> float:
        if audio_duration_sec <= 0:
            return 0.0
        wpm = (word_count / audio_duration_sec) * 60.0
        return wpm
