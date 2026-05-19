import logging
import math
from typing import Dict

logger = logging.getLogger(__name__)


class CEOVoiceDeceptionAgent:
    """
    Analyses CEO earnings call audio for stress biomarkers.
    Uses fundamental frequency (F0) jitter and shimmer as deception proxies.
    High jitter (>3%) + high shimmer (>5%) = elevated stress = potential bad news.
    """

    JITTER_THRESHOLD = 0.03
    SHIMMER_THRESHOLD = 0.05

    def analyse_prosody(self, f0_values: list[float], amplitude_values: list[float]) -> Dict:
        """
        f0_values: list of pitch values in Hz per frame.
        amplitude_values: list of RMS amplitude per frame.
        """
        if len(f0_values) < 10 or len(amplitude_values) < 10:
            return {"stress_score": 0.0, "verdict": "INSUFFICIENT_DATA"}
        # Jitter: frame-to-frame F0 variation
        jitter = sum(abs(f0_values[i] - f0_values[i - 1]) for i in range(1, len(f0_values)))
        jitter /= len(f0_values) * (sum(f0_values) / len(f0_values) + 1e-9)
        # Shimmer: frame-to-frame amplitude variation
        shimmer = sum(
            abs(amplitude_values[i] - amplitude_values[i - 1])
            for i in range(1, len(amplitude_values))
        )
        shimmer /= len(amplitude_values) * (sum(amplitude_values) / len(amplitude_values) + 1e-9)
        stress = min(1.0, (jitter / self.JITTER_THRESHOLD + shimmer / self.SHIMMER_THRESHOLD) / 2)
        verdict = "HIGH_STRESS" if stress > 0.7 else "MODERATE" if stress > 0.4 else "CALM"
        logger.info(
            f"[VOICE] Jitter={jitter:.3f} Shimmer={shimmer:.3f} Stress={stress:.2f} -> {verdict}"
        )
        return {
            "stress_score": round(stress, 3),
            "jitter": round(jitter, 4),
            "shimmer": round(shimmer, 4),
            "verdict": verdict,
        }
