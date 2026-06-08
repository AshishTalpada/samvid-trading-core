"""Tests for the per-signal Information Coefficient diagnostic."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for _path in (ROOT / "scripts", ROOT / "src"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))


def test_compute_ic_detects_perfect_positive_correlation():
    from signal_ic_diagnostic import compute_ic

    scores = list(np.linspace(-1.0, 1.0, 100))
    forwards = list(np.linspace(-0.02, 0.02, 100))
    ic = compute_ic(scores, forwards)
    assert ic["pearson_r"] > 0.99
    assert ic["pearson_p"] < 0.01
    assert ic["n"] == 100


def test_compute_ic_detects_anti_correlation():
    from signal_ic_diagnostic import compute_ic

    scores = list(np.linspace(-1.0, 1.0, 100))
    forwards = list(np.linspace(0.02, -0.02, 100))
    ic = compute_ic(scores, forwards)
    assert ic["pearson_r"] < -0.99
    assert ic["pearson_p"] < 0.01


def test_compute_ic_handles_degenerate_input():
    from signal_ic_diagnostic import compute_ic

    # Constant scores -> zero variance -> no IC, must not raise.
    ic = compute_ic([0.5] * 50, list(np.random.default_rng(0).normal(size=50)))
    assert ic["pearson_r"] == 0.0
    assert ic["pearson_p"] == 1.0

    # Too few samples.
    ic_small = compute_ic([1.0, 2.0, 3.0], [0.1, 0.2, 0.3])
    assert ic_small["n"] == 3
    assert ic_small["pearson_r"] == 0.0


def test_signal_ics_for_symbol_returns_all_signals():
    from signal_ic_diagnostic import signal_ics_for_symbol

    rng = np.random.default_rng(7)
    closes = 100.0 + np.cumsum(rng.normal(0, 0.5, 600))
    volumes = np.abs(rng.normal(1000, 100, 600))
    ics = signal_ics_for_symbol(closes, volumes, "TEST", horizon=10, stride=5, lookback=200)
    assert set(ics) == {"alpha", "kalman", "combined"}
    for ic in ics.values():
        assert ic["n"] > 0
        assert -1.0 <= ic["pearson_r"] <= 1.0
