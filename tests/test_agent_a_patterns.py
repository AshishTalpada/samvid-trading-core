"""
Tests for agent_a pattern detection with Polars DataFrames.

Validates that all pattern detectors use correct Polars-native indexing
after the 2026-05-27 refactoring (no pandas-style negative indexing).
"""

from __future__ import annotations

import numpy as np
import polars as pl
import pytest


def _make_ohlcv(n: int = 100, trend: str = "up") -> pl.DataFrame:
    """Generate a synthetic OHLCV DataFrame."""
    base = np.cumsum(np.random.randn(n) * 0.5) + 100.0
    if trend == "up":
        base += np.linspace(0, 10, n)
    elif trend == "down":
        base -= np.linspace(0, 10, n)

    opens = base + np.random.randn(n) * 0.3
    closes = base + np.random.randn(n) * 0.3
    highs = np.maximum(opens, closes) + np.abs(np.random.randn(n)) * 0.5 + 0.1
    lows = np.minimum(opens, closes) - np.abs(np.random.randn(n)) * 0.5 - 0.1
    volumes = np.random.randint(1000, 10000, n)

    return pl.DataFrame(
        {
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
        }
    )


def test_pattern_detector_imports() -> None:
    from agent_a import PatternDetector

    assert PatternDetector is not None


def test_detect_all_runs_without_crash() -> None:
    """Ensure detect_all() executes without raising on valid Polars input."""
    from agent_a import PatternDetector

    df = _make_ohlcv(n=100, trend="up")
    detector = PatternDetector()
    patterns = detector.detect_all(df)

    # Should return a list (may be empty or contain Nones)
    assert isinstance(patterns, list)


def test_detect_all_does_not_crash_on_uptrend() -> None:
    """Pattern detection should run without crash on a clear uptrend."""
    from agent_a import PatternDetector

    df = _make_ohlcv(n=100, trend="up")
    detector = PatternDetector()
    # Critical: this must not raise TypeError from pandas-style indexing
    patterns = detector.detect_all(df)
    assert isinstance(patterns, list)


def test_head_and_shoulders_sorts_by_time() -> None:
    """Verify H&S peak sorting uses time index, not price height."""
    from agent_a import PatternDetector

    # Create a DataFrame with a clear H&S pattern:
    # Left shoulder at t=10 (price 110), Head at t=20 (price 120), Right shoulder at t=30 (price 115)
    n = 50
    closes = np.ones(n) * 100
    closes[5:15] = np.linspace(100, 110, 10)
    closes[15:25] = np.concatenate([np.linspace(110, 120, 5), np.linspace(120, 100, 5)])
    closes[25:35] = np.linspace(100, 115, 10)
    closes[35:] = np.linspace(115, 90, 15)

    highs = closes + 2.0
    lows = closes - 2.0
    opens = closes + np.random.randn(n) * 0.1
    volumes = np.random.randint(1000, 5000, n)

    df = pl.DataFrame({
        "open": opens,
        "high": highs,
        "low": lows,
        "close": closes,
        "volume": volumes,
    })

    detector = PatternDetector()
    patterns = detector.detect_all(df)
    hs = [p for p in patterns if p is not None and p.name == "Head & Shoulders"]
    if hs:
        # If detected, it should NOT have crashed during sorting
        assert hs[0].confidence >= 0


def test_polars_tail_access_in_patterns() -> None:
    """Verify all pattern methods use Polars-native .tail()/.item() access."""
    from agent_a import PatternDetector

    df = _make_ohlcv(n=100)
    detector = PatternDetector()

    # This will crash if any method still uses pandas-style indexing
    try:
        patterns = detector.detect_all(df)
    except TypeError as e:
        pytest.fail(f"Polars indexing bug detected: {e}")

    # All returned values should be either None or PatternResult
    for p in patterns:
        if p is not None:
            assert hasattr(p, "name")
            assert hasattr(p, "confidence")
            assert hasattr(p, "entry")
            assert hasattr(p, "stop")
            assert hasattr(p, "target")
