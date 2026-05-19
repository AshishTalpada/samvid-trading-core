import logging
import math
from typing import List

logger = logging.getLogger(__name__)


class BCIGateway:
    """
    Brain-Computer Interface gateway for real-time cognitive state integration.
    Classifies alpha/beta/theta/gamma band power from EEG electrode arrays.
    Gates trading authorization based on cognitive clarity score.
    """

    BANDS = {
        "delta": (0.5, 4),
        "theta": (4, 8),
        "alpha": (8, 13),
        "beta": (13, 30),
        "gamma": (30, 100),
    }
    CLARITY_THRESHOLD = 0.55

    def compute_band_power(self, eeg_signal: List[float], sampling_rate: float, band: str) -> float:
        low, high = self.BANDS.get(band, (8, 13))
        n = len(eeg_signal)
        if n < 4:
            return 0.0
        dt = 1.0 / sampling_rate
        freqs = [i / (n * dt) for i in range(n // 2)]
        fft_mag = [
            abs(sum(eeg_signal[j] * math.cos(2 * math.pi * freqs[k] * j * dt) for j in range(n)))
            / n
            for k in range(len(freqs))
        ]
        band_power = sum(fft_mag[i] ** 2 for i, f in enumerate(freqs) if low <= f <= high)
        return round(band_power, 6)

    def cognitive_clarity(self, eeg_signal: List[float], sampling_rate: float = 256.0) -> float:
        alpha = self.compute_band_power(eeg_signal, sampling_rate, "alpha")
        beta = self.compute_band_power(eeg_signal, sampling_rate, "beta")
        theta = self.compute_band_power(eeg_signal, sampling_rate, "theta")
        total = alpha + beta + theta + 1e-9
        clarity = (beta * 0.6 + alpha * 0.4) / total
        return round(min(1.0, clarity), 3)

    def authorize_trade(self, eeg_signal: List[float]) -> bool:
        clarity = self.cognitive_clarity(eeg_signal)
        authorized = clarity >= self.CLARITY_THRESHOLD
        logger.info(f"[BCI] Clarity={clarity:.2f} -> {'AUTHORIZED' if authorized else 'BLOCKED'}")
        return authorized
