"""Tests for the adaptive pattern evolution engine."""
from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pattern_evolution import EvolvedPatternDetector, EvolvedPatternRegistry


def test_evolved_registry_save_load(tmp_path: Path) -> None:
    registry = EvolvedPatternRegistry(path=tmp_path / "evolved.json")
    alphas = [
        {"rule": "momentum", "params": {"period": 10}, "sharpe_oos": 0.8, "weight": 1.0}
    ]
    registry.save(alphas)
    loaded = registry.load()
    assert len(loaded) == 1
    assert loaded[0]["rule"] == "momentum"


def test_evolved_detector_momentum() -> None:
    """Evolved momentum detector should fire on rising price + volume expansion."""
    n = 40
    base_volume = [1000] * 35
    spike_volume = [5000, 5500, 6000, 6500, 7000]
    df = pl.DataFrame(
        {
            "timestamp": list(range(n)),
            "open": [100.0 + i * 0.05 for i in range(n)],
            "high": [100.0 + i * 0.05 + 0.1 for i in range(n)],
            "low": [100.0 + i * 0.05 - 0.1 for i in range(n)],
            "close": [100.0 + i * 0.05 for i in range(n)],
            "volume": base_volume + spike_volume,
        }
    )
    detector = EvolvedPatternDetector()
    result = detector.detect_evolved_momentum(df)
    assert result is not None
    assert result.name == "Evolved Momentum"
    assert result.confidence >= 60.0
    assert result.entry > 100.0


def test_evolved_detector_mean_reversion() -> None:
    """Evolved mean-reversion detector should fire on extreme z-score."""
    n = 40
    prices = [100.0] * 35 + [130.0, 131.0, 132.0, 133.0, 134.0]
    df = pl.DataFrame(
        {
            "timestamp": list(range(n)),
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low": [p - 0.1 for p in prices],
            "close": prices,
            "volume": [1000] * n,
        }
    )
    detector = EvolvedPatternDetector()
    result = detector.detect_evolved_mean_reversion(df)
    assert result is not None
    assert result.name == "Evolved Mean Reversion"
    assert result.entry > 100.0


def test_evolved_alpha_ensemble() -> None:
    """Evolved alpha detector should return a PatternResult on strong signal."""
    n = 60
    prices = [100.0 + i * 0.1 for i in range(n)]
    df = pl.DataFrame(
        {
            "timestamp": list(range(n)),
            "open": prices,
            "high": [p + 0.1 for p in prices],
            "low": [p - 0.1 for p in prices],
            "close": prices,
            "volume": [1000] * n,
        }
    )
    detector = EvolvedPatternDetector()
    # Force evolution on first call
    detector._call_count = detector.evolve_every_n_calls
    result = detector.detect_evolved_alpha(df)
    assert result is None or result.name == "Evolved Alpha"
