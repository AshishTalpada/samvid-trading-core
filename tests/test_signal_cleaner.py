import numpy as np

from signal_cleaner import WaveletSignalCleaner


def test_signal_cleaner_imports_and_returns_same_length() -> None:
    cleaner = WaveletSignalCleaner()
    prices = [100.0, 101.0, 99.5, 102.0, 101.5, 103.0, 102.5]

    cleaned = cleaner.clean(prices)

    assert isinstance(cleaned, np.ndarray)
    assert len(cleaned) == len(prices)
    assert np.isfinite(cleaned).all()


def test_signal_cleaner_handles_empty_series() -> None:
    cleaner = WaveletSignalCleaner()

    cleaned = cleaner.clean([])

    assert len(cleaned) == 0
