import logging
import math
import time

import numpy as np

logger = logging.getLogger(__name__)


class BCISignalProcessor:
    """
    Brain-Computer Interface (BCI) EEG Signal Adapter.
    Designed to interface with OpenBCI or Emotiv EPOC hardware via LSL (Lab Streaming Layer).
    Processes raw EEG alpha/beta/gamma band power to detect trader cognitive states
    (focus, fatigue, stress) and feed this as a real-time bias correction signal
    into the quorum system.
    """

    BAND_RANGES = {
        "delta": (0.5, 4.0),
        "theta": (4.0, 8.0),
        "alpha": (8.0, 13.0),
        "beta":  (13.0, 30.0),
        "gamma": (30.0, 100.0),
    }

    def __init__(self, sample_rate: float = 250.0) -> None:
        self.sample_rate = sample_rate

    def compute_band_power(self, eeg_signal: np.ndarray, band: str) -> float:
        """
        Computes the power spectral density in a specific EEG frequency band
        using Welch's method via FFT.

        :param eeg_signal: 1D numpy array of raw EEG samples
        :param band: One of 'delta', 'theta', 'alpha', 'beta', 'gamma'
        """
        if band not in self.BAND_RANGES:
            raise ValueError(f"Unknown EEG band: {band}")

        low, high = self.BAND_RANGES[band]
        n = len(eeg_signal)
        if n < 2:
            return 0.0

        # Apply Hanning window to reduce spectral leakage
        window = np.hanning(n)
        windowed = eeg_signal * window

        # Compute FFT and power spectrum
        fft_vals = np.fft.rfft(windowed)
        power = (np.abs(fft_vals) ** 2) / n
        freqs = np.fft.rfftfreq(n, d=1.0 / self.sample_rate)

        # Integrate power within band
        band_mask = (freqs >= low) & (freqs < high)
        band_power = float(np.sum(power[band_mask]))
        return band_power

    def classify_cognitive_state(self, eeg_signal: np.ndarray) -> dict[str, float | str]:
        """
        Classifies the trader's current cognitive state.
        High beta → stress/overtrading risk
        High alpha → calm focus → trust signals
        High theta → fatigue/impaired judgment → reduce position sizing
        """
        alpha = self.compute_band_power(eeg_signal, "alpha")
        beta = self.compute_band_power(eeg_signal, "beta")
        theta = self.compute_band_power(eeg_signal, "theta")

        total = alpha + beta + theta + 1e-9

        alpha_ratio = alpha / total
        beta_ratio = beta / total
        theta_ratio = theta / total

        if beta_ratio > 0.5:
            state = "STRESS"
            confidence_modifier = 0.7
        elif theta_ratio > 0.4:
            state = "FATIGUE"
            confidence_modifier = 0.6
        elif alpha_ratio > 0.45:
            state = "FOCUSED"
            confidence_modifier = 1.0
        else:
            state = "NEUTRAL"
            confidence_modifier = 0.9

        logger.info(f"[BCI] Cognitive state: {state} | α={alpha_ratio:.2f} β={beta_ratio:.2f} θ={theta_ratio:.2f}")
        return {
            "state": state,
            "confidence_modifier": confidence_modifier,
            "alpha_ratio": round(alpha_ratio, 3),
            "beta_ratio": round(beta_ratio, 3),
            "theta_ratio": round(theta_ratio, 3),
        }
