import numpy as np

try:
    import pywt
except ImportError:  # pragma: no cover - exercised through import behavior in lean envs
    pywt = None


class WaveletSignalCleaner:
    """
    Removes market microstructure noise from price series via wavelet decomposition.
    Uses Daubechies db4 wavelets which are optimally matched to financial time series.
    Separates True Trend (low-frequency) from noise (high-frequency detail coefficients).
    """

    def __init__(self, wavelet: str = "db4", level: int = 4, threshold_mode: str = "soft"):
        self.wavelet = wavelet
        self.level = level
        self.mode = threshold_mode

    def clean(self, prices: list[float]) -> np.ndarray:
        arr = np.array(prices, dtype=float)
        if len(arr) == 0:
            return arr
        if pywt is None:
            window = min(7, max(1, len(arr)))
            kernel = np.ones(window, dtype=float) / window
            padded = np.pad(arr, (window // 2, window - 1 - window // 2), mode="edge")
            return np.convolve(padded, kernel, mode="valid")[: len(arr)]

        coeffs = pywt.wavedec(arr, self.wavelet, level=self.level)
        # Universal threshold: sigma * sqrt(2 * log(n))
        sigma = np.median(np.abs(coeffs[-1])) / 0.6745
        threshold = sigma * np.sqrt(2 * np.log(len(arr)))
        # Zero out high-frequency noise detail coefficients
        coeffs[1:] = [pywt.threshold(c, threshold, mode=self.mode) for c in coeffs[1:]]
        return pywt.waverec(coeffs, self.wavelet)[: len(arr)]  # type: ignore

    def trend_strength(self, prices: list[float]) -> float:
        """Returns 0.0 (pure noise) to 1.0 (clean trend). Uses ratio of signal energy."""
        cleaned = self.clean(prices)
        orig = np.array(prices)
        signal_power = float(np.var(cleaned))
        total_power = float(np.var(orig)) + 1e-12
        return min(1.0, signal_power / total_power)
