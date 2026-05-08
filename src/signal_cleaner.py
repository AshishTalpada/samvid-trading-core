"""
Signal Cleaner (#107 from SOVEREIGN_ULTIMATE_CHECKLIST).
Wavelet-based de-noising to separate 'Market Noise' from 'True Trend'.
"""

import logging
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class WaveletDenoiseResult:
    """Result of wavelet denoising operation."""
    original: np.ndarray
    denoised: np.ndarray
    noise: np.ndarray
    snr: float
    decomposition_level: int


class SignalCleaner:
    """
    Wavelet-based signal cleaning to separate market noise from true trends.
    
    Uses PyWavelets (pywt) for multi-resolution decomposition and thresholding.
    """

    SUPPORTED_WAVELETS = [
        "db4", "db6", "db8", "sym4", "sym6", "coif3", "haar"
    ]

    DEFAULT_WAVELET = "db4"
    DEFAULT_THRESHOLD_MODE = "soft"

    def __init__(self, wavelet: str = "db4", threshold_mode: str = "soft"):
        self.wavelet = wavelet
        self.threshold_mode = threshold_mode
        self._pywt: Any = None
        self._try_import_pywt()

    def _try_import_pywt(self):
        """Try to import pywt, fall back to manual implementation if unavailable."""
        try:
            import pywt
            self._pywt = pywt
        except ImportError:
            logger.warning("PyWavelets (pywt) not available. Using manual wavelet implementation.")
            self._pywt = None

    def denoise(
        self,
        signal: list[float] | None,
        level: int = 4,
        threshold_multiplier: float = 1.0,
    ) -> WaveletDenoiseResult:
        """
        Apply wavelet denoising to remove market noise.
        """
        if signal is None or len(signal) == 0:
            return WaveletDenoiseResult(
                original=np.array([]),
                denoised=np.array([]),
                noise=np.array([]),
                snr=0.0,
                decomposition_level=0,
            )

        if len(signal) < 2**level:
            logger.warning(f"Signal too short for decomposition level {level}")
            level = int(np.log2(len(signal))) - 1

        signal_arr = np.array(signal, dtype=np.float64)

        if self._pywt is not None:
            denoised, noise, threshold = self._denoise_with_pywt(
                signal_arr, level, threshold_multiplier
            )
        else:
            denoised, noise, threshold = self._denoise_manual(
                signal_arr, level, threshold_multiplier
            )

        snr = self._calculate_snr(signal_arr, noise)

        return WaveletDenoiseResult(
            original=signal_arr,
            denoised=denoised,
            noise=noise,
            snr=snr,
            decomposition_level=level,
        )

    def _denoise_with_pywt(
        self,
        signal: np.ndarray,
        level: int,
        threshold_mult: float,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        from typing import cast
        pywt_lib = cast(Any, self._pywt)
        coeffs = pywt_lib.wavedec(signal, self.wavelet, level=level)

        sigma = self._estimate_noise_sigma(coeffs[-1])
        threshold = sigma * np.sqrt(2 * np.log(len(signal))) * threshold_mult

        denoised_coeffs = [coeffs[0]]
        for c in coeffs[1:]:
            denoised_coeffs.append(pywt_lib.threshold(c, threshold, mode=self.threshold_mode))

        denoised = pywt_lib.waverec(denoised_coeffs, self.wavelet)

        if len(denoised) > len(signal):
            denoised = denoised[:len(signal)]
        elif len(denoised) < len(signal):
            denoised = np.pad(denoised, (0, len(signal) - len(denoised)))

        noise = signal - denoised

        return denoised, noise, threshold

    def _denoise_manual(
        self,
        signal: np.ndarray,
        level: int,
        threshold_mult: float,
    ) -> tuple[np.ndarray, np.ndarray, float]:
        """Manual wavelet denoising using simple Haar-like decomposition."""
        n = len(signal)

        approx = signal.copy()
        details = []

        for _ in range(level):
            if len(approx) < 4:
                break

            half = len(approx) // 2
            low = np.array([(approx[2*i] + approx[2*i+1]) / 2 for i in range(half)])
            high = np.array([(approx[2*i] - approx[2*i+1]) / 2 for i in range(half)])

            details.append(high)
            approx = low

        sigma = np.std(details[-1]) if details else np.std(signal) * 0.5
        threshold = sigma * np.sqrt(2 * np.log(n)) * threshold_mult

        for i in range(len(details)):
            details[i] = np.where(np.abs(details[i]) < threshold, 0, details[i])
            if self.threshold_mode == "soft":
                details[i] = np.sign(details[i]) * (np.abs(details[i]) - threshold)

        denoised = approx.copy()
        for detail in reversed(details):
            denoised = np.repeat(denoised, 2)
            denoised[:len(detail)] += detail

        noise = signal - denoised[:len(signal)]

        return denoised[:len(signal)], noise, threshold

    def _estimate_noise_sigma(self, detail_coeffs: np.ndarray) -> float:
        """Estimate noise standard deviation from finest detail coefficients."""
        return np.median(np.abs(detail_coeffs)) / 0.6745

    def _calculate_snr(self, original: np.ndarray, noise: np.ndarray) -> float:
        """Calculate Signal-to-Noise Ratio in dB."""
        signal_power = np.mean(original ** 2)
        noise_power = np.mean(noise ** 2)

        if noise_power < 1e-10:
            return 100.0

        snr_linear = signal_power / noise_power
        return 10 * np.log10(snr_linear)

    def extract_trend(
        self,
        prices: list[float],
        noise_tolerance: float = 0.05,
    ) -> dict[str, Any]:
        """
        Extract the true trend from noisy price data.
        
        Args:
            prices: Raw price data
            noise_tolerance: Maximum allowed noise ratio (0-1)
            
        Returns:
            Dictionary with trend, noise, and quality metrics
        """
        if len(prices) < 32:
            return {
                "trend": prices,
                "noise": [],
                "quality": "INSUFFICIENT_DATA",
                "snr_db": 0.0,
            }

        result = self.denoise(prices, level=4)

        quality = "HIGH"
        if result.snr < 10:
            quality = "LOW"
        elif result.snr < 20:
            quality = "MEDIUM"

        noise_ratio = np.std(result.noise) / np.std(result.original)
        if noise_ratio > noise_tolerance:
            quality = "NOISY"

        return {
            "trend": result.denoised.tolist(),
            "noise": result.noise.tolist(),
            "quality": quality,
            "snr_db": result.snr,
            "decomposition_level": result.decomposition_level,
            "original": result.original.tolist(),
        }

    def decompose_levels(
        self,
        signal: list[float],
        max_level: int = 5,
    ) -> dict[str, Any]:
        """
        Multi-level wavelet decomposition for detailed analysis.
        
        Returns:
            Dictionary with approximation and detail coefficients at each level
        """
        signal_arr = np.array(signal)
        decomposition: dict[str, Any] = {"levels": [], "error": []}
        decomposition["error"] = [] # Initialize as list to satisfy TypedDict inference if present

        if self._pywt is not None:
            try:
                coeffs = self._pywt.wavedec(signal_arr, self.wavelet, level=max_level)

                decomposition["levels"].append({
                    "level": 0,
                    "type": "approximation",
                    "data": coeffs[0].tolist(),
                })

                for i, detail in enumerate(coeffs[1:], 1):
                    decomposition["levels"].append({
                        "level": i,
                        "type": "detail",
                        "data": detail.tolist(),
                    })
            except Exception as e:
                logger.error(f"Wavelet decomposition failed: {e}")
                decomposition["error"] = [str(e)]
        else:
            decomposition["error"] = ["PyWavelets not available"]

        return decomposition


_signal_cleaner_instance: Optional[SignalCleaner] = None


def get_signal_cleaner() -> SignalCleaner:
    """Get the singleton SignalCleaner instance."""
    global _signal_cleaner_instance
    if _signal_cleaner_instance is None:
        _signal_cleaner_instance = SignalCleaner()
    return _signal_cleaner_instance
