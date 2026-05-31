from __future__ import annotations

import numpy as np
import pytest

from quant_math import ema_array, macd_array, rsi_array


def _first_valid_index(values: np.ndarray) -> int | None:
    indices = np.flatnonzero(~np.isnan(values))
    return int(indices[0]) if len(indices) else None


def test_ema_recovers_after_leading_nan_values() -> None:
    values = np.array([np.nan, np.nan, 1.0, 2.0, 3.0, 4.0])

    result = ema_array(values, 3)

    assert np.isnan(result[:4]).all()
    assert result[4] == pytest.approx(2.25)
    assert result[5] == pytest.approx(3.125)


def test_ema_accepts_empty_input() -> None:
    assert ema_array(np.array([], dtype=np.float64), 3).size == 0


def test_ema_rejects_non_positive_period() -> None:
    with pytest.raises(ValueError, match="period must be positive"):
        ema_array(np.array([1.0]), 0)


def test_rsi_publishes_initial_value_at_wilder_boundary() -> None:
    prices = np.linspace(100.0, 114.0, 15)

    result = rsi_array(prices, 14)

    assert np.isnan(result[:14]).all()
    assert result[14] == pytest.approx(100.0)


def test_macd_signal_recovers_after_slow_ema_warmup() -> None:
    prices = np.linspace(100.0, 130.0, 80)

    macd, signal, histogram = macd_array(prices)

    assert _first_valid_index(macd) == 25
    assert _first_valid_index(signal) == 33
    assert _first_valid_index(histogram) == 33
    assert np.isfinite(signal[-1])
    assert np.isfinite(histogram[-1])
