"""Regression tests for the regime-vote wiring in QuantConsensus.

The HMM RegimeFilter used to emit its regime *name* ("BULL"/"BEAR") as the vote,
which never matched the "BUY"/"SELL" labels the consensus tally and regime_veto
compared against. That made the regime confidence dilute the denominator without
ever contributing to a direction, and made regime_veto impossible to trigger.
"""

from __future__ import annotations

import numpy as np

from quant_signals import QuantConsensus, SignalResult


def _force_signals(monkeypatch, qc, regime, alpha, entry):
    monkeypatch.setattr(qc.regime_filter, "predict", lambda prices: regime)
    monkeypatch.setattr(qc.alpha_model, "compute", lambda *a, **k: alpha)
    monkeypatch.setattr(qc.entry_timer, "compute", lambda *a, **k: entry)


def test_bearish_regime_vetoes_a_bullish_consensus(monkeypatch):
    qc = QuantConsensus()
    _force_signals(
        monkeypatch,
        qc,
        regime=SignalResult("regime", -0.8, 0.9, "SELL", {"regime": "BEAR"}),
        alpha=SignalResult("multi_factor", 0.5, 0.9, "BUY"),
        entry=SignalResult("kalman_entry", 0.5, 0.9, "BUY"),
    )

    out = qc.evaluate("SPY", np.ones(50), np.ones(50))

    assert out["regime_veto"] == 1, "bearish regime must veto a BUY consensus"
    assert out["phase"] == "HOLD"


def test_regime_confidence_now_counts_toward_direction(monkeypatch):
    qc = QuantConsensus()
    # Alpha alone (0.4/total) would fall below the 0.45 threshold; the bullish
    # regime vote must push the BUY consensus over the line.
    _force_signals(
        monkeypatch,
        qc,
        regime=SignalResult("regime", 0.8, 0.9, "BUY", {"regime": "BULL"}),
        alpha=SignalResult("multi_factor", 0.2, 0.6, "BUY"),
        entry=SignalResult("kalman_entry", 0.0, 0.9, "NEUTRAL"),
    )

    out = qc.evaluate("SPY", np.ones(50), np.ones(50))

    assert out["phase"] == "BUY"
    assert out["regime_veto"] == 0
    assert out["bias"] == "BULLISH"


def test_regime_predict_without_model_is_neutral():
    from quant_signals import RegimeFilter

    result = RegimeFilter().predict(np.linspace(100.0, 110.0, 60))
    assert result.vote == "NEUTRAL"
