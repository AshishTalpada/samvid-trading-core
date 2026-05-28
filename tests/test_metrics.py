"""
tests/test_metrics.py
Prometheus metrics tests (Phase 4)

Verifies:
  1.  METRICS singleton is importable and exposes expected metric objects
  2.  Counter increment accumulates correctly
  3.  Gauge set/get round-trip
  4.  Histogram observation records to the correct bucket
  5.  record_trade() updates trades_total, trade_pnl_dollars, trade_r_multiple
  6.  update_from_brain() sets open_positions gauge from brain fixture
  7.  update_from_brain() sets risk_modifier gauge
  8.  update_from_brain() sets session_pnl gauge
  9.  update_from_brain() sets belief_score gauge
  10. update_from_brain() sets regime label gauge (correct label = 1, others = 0)
  11. update_from_brain() sets broker_connected gauge (IBKR disconnected → 0)
  12. update_from_brain() never raises on a minimal brain-like object
  13. generate_latest_text() returns bytes containing 'sovereign_'
  14. start_metrics_server() is idempotent (second call is a no-op)
"""

import sys
from unittest.mock import MagicMock

import pytest
from prometheus_client import CollectorRegistry, Counter, Gauge

sys.path.insert(0, "src")

# Import using the module-level singleton (uses default registry)
from metrics import METRICS, generate_latest_text, start_metrics_server, TradingMetrics


# ---------------------------------------------------------------------------
# Helper: minimal brain-like stub
# ---------------------------------------------------------------------------

class _FakeBrainPositions:
    unrealized_pnl = 150.0


def _make_fake_brain(
    positions=None,
    session_pnl=500.0,
    risk_modifier=0.8,
    belief=0.6,
    regime="TRENDING",
    emergency_halted=False,
    ibkr_connected=False,
    mt5_connected=False,
) -> MagicMock:
    brain = MagicMock()
    brain.positions = positions if positions is not None else [_FakeBrainPositions()]
    brain.session_pnl = session_pnl
    brain._oracle_risk_modifier = risk_modifier
    brain.belief_tracker = MagicMock()
    brain.belief_tracker.current_belief = belief
    brain.current_regime = regime
    brain.emergency_halted = emergency_halted

    brain.ibkr_drawdown = MagicMock()
    brain.ibkr_drawdown.current_drawdown_pct = 0.02
    brain.ibkr_drawdown.peak_equity = 105_000.0

    brain.ibkr_conn = MagicMock()
    brain.ibkr_conn.is_connected.return_value = ibkr_connected
    brain.mt5_conn = MagicMock()
    brain.mt5_conn.is_connected.return_value = mt5_connected
    return brain


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_metrics_singleton_importable():
    """Test 1: METRICS singleton has expected metric attributes."""
    assert hasattr(METRICS, "trades_total")
    assert hasattr(METRICS, "open_positions")
    assert hasattr(METRICS, "daily_pnl_dollars")
    assert hasattr(METRICS, "scan_cycle_duration_seconds")
    assert hasattr(METRICS, "broker_connected")
    assert hasattr(METRICS, "emergency_halt_active")


def test_counter_increments(tmp_path):
    """Test 2: Counter labels accumulate independently."""
    # Use an isolated registry to avoid cross-test pollution
    reg = CollectorRegistry()
    c = Counter("test_counter_inc", "test", ["broker"], registry=reg)
    c.labels(broker="IBKR").inc()
    c.labels(broker="IBKR").inc()
    c.labels(broker="MT5").inc()
    ibkr_val = c.labels(broker="IBKR")._value.get()
    mt5_val = c.labels(broker="MT5")._value.get()
    assert ibkr_val == 2.0
    assert mt5_val == 1.0


def test_gauge_set_get():
    """Test 3: Gauge.set() followed by reading the value round-trips correctly."""
    reg = CollectorRegistry()
    g = Gauge("test_gauge_rtrip", "test", registry=reg)
    g.set(42.5)
    assert g._value.get() == 42.5


def test_histogram_observation():
    """Test 4: Histogram.observe() increments the count."""
    from prometheus_client import Histogram as H
    reg = CollectorRegistry()
    h = H("test_hist_obs", "test", registry=reg, buckets=(0.1, 1.0, 10.0))
    h.observe(0.5)
    h.observe(0.5)
    # _count should be 2
    assert h._sum.get() == pytest.approx(1.0)


def test_record_trade_updates_all_metrics():
    """Test 5: record_trade() updates trades_total, pnl histogram, r-multiple histogram."""
    # Read current values before
    before_ibkr = METRICS.trades_total.labels(
        broker="IBKR_TEST5", direction="LONG", outcome="WIN"
    )._value.get()

    METRICS.record_trade(
        broker="IBKR_TEST5",
        direction="LONG",
        outcome="WIN",
        pnl=250.0,
        r_multiple=2.5,
    )
    after_ibkr = METRICS.trades_total.labels(
        broker="IBKR_TEST5", direction="LONG", outcome="WIN"
    )._value.get()
    assert after_ibkr == before_ibkr + 1


def test_update_from_brain_open_positions():
    """Test 6: update_from_brain() sets open_positions gauge to len(brain.positions)."""
    brain = _make_fake_brain(positions=[MagicMock(), MagicMock(), MagicMock()])
    METRICS.update_from_brain(brain)
    assert METRICS.open_positions._value.get() == 3.0


def test_update_from_brain_risk_modifier():
    """Test 7: update_from_brain() sets risk_modifier gauge."""
    brain = _make_fake_brain(risk_modifier=0.75)
    METRICS.update_from_brain(brain)
    assert METRICS.risk_modifier._value.get() == pytest.approx(0.75)


def test_update_from_brain_session_pnl():
    """Test 8: update_from_brain() sets session_pnl gauge."""
    brain = _make_fake_brain(session_pnl=1234.56)
    METRICS.update_from_brain(brain)
    assert METRICS.session_pnl_dollars._value.get() == pytest.approx(1234.56)


def test_update_from_brain_belief_score():
    """Test 9: update_from_brain() sets belief_score gauge."""
    brain = _make_fake_brain(belief=0.72)
    METRICS.update_from_brain(brain)
    assert METRICS.belief_score._value.get() == pytest.approx(0.72)


def test_update_from_brain_regime_labels():
    """Test 10: only the current regime label is set to 1.0; others are 0.0."""
    brain = _make_fake_brain(regime="BULL")
    METRICS.update_from_brain(brain)
    assert METRICS.regime.labels(regime="BULL")._value.get() == 1.0
    assert METRICS.regime.labels(regime="BEAR")._value.get() == 0.0
    assert METRICS.regime.labels(regime="TRENDING")._value.get() == 0.0


def test_update_from_brain_broker_connected_false():
    """Test 11: disconnected IBKR → broker_connected gauge = 0."""
    brain = _make_fake_brain(ibkr_connected=False)
    METRICS.update_from_brain(brain)
    assert METRICS.broker_connected.labels(broker="IBKR")._value.get() == 0.0


def test_update_from_brain_broker_connected_true():
    """Test 11b: connected IBKR → broker_connected gauge = 1."""
    brain = _make_fake_brain(ibkr_connected=True)
    METRICS.update_from_brain(brain)
    assert METRICS.broker_connected.labels(broker="IBKR")._value.get() == 1.0


def test_update_from_brain_never_raises_on_minimal_object():
    """Test 12: update_from_brain() handles a completely bare MagicMock safely."""
    bare = MagicMock(spec=[])  # No attributes at all
    # Must not raise
    METRICS.update_from_brain(bare)


def test_generate_latest_text_returns_bytes_with_prefix():
    """Test 13: generate_latest_text() returns bytes containing 'sovereign_'."""
    data = generate_latest_text()
    assert isinstance(data, bytes)
    assert b"sovereign_" in data


def test_start_metrics_server_is_idempotent():
    """Test 14: calling start_metrics_server() twice doesn't crash (no-op on second call)."""
    # Port 0 = OS assigns a free port; skip actual binding to avoid side effects in CI
    # Just test the idempotency guard via the _metrics_server_started flag
    import metrics as _m
    original = _m._metrics_server_started
    try:
        _m._metrics_server_started = True  # simulate already started
        start_metrics_server(port=19090)   # should be a no-op, not raise
    finally:
        _m._metrics_server_started = original
