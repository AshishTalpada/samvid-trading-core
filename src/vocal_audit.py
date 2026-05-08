import logging
import statistics
from typing import Dict, List

logger = logging.getLogger(__name__)

class VocalJitterAuditor:
    """
    Micro-jitter auditor for executive voice analysis.
    Measures millisecond-level pause patterns and speech rate deceleration
    as stress biomarkers during high-stakes earnings calls.
    """
    def compute_pause_stats(self, pause_durations_ms: List[float]) -> Dict:
        if not pause_durations_ms:
            return {"mean_pause": 0.0, "std_pause": 0.0, "stress_indicator": False}
        mean = statistics.mean(pause_durations_ms)
        std = statistics.stdev(pause_durations_ms) if len(pause_durations_ms) > 1 else 0.0
        cv = std / mean if mean > 0 else 0.0
        stress = cv > 0.6 or mean > 800  # Coefficient of variation > 60% or mean pause > 800ms
        logger.info(f"[VOCAL] Mean pause={mean:.0f}ms CV={cv:.2f} Stress={stress}")
        return {"mean_pause": round(mean, 1), "std_pause": round(std, 1), "cv": round(cv, 3), "stress_indicator": stress}

    def compute_speech_rate(self, word_count: int, duration_seconds: float) -> float:
        return word_count / (duration_seconds / 60.0) if duration_seconds > 0 else 0.0
