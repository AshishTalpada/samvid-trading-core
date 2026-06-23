"""
tests/test_brain_mixins.py
Comprehensive tests for brain mixin modules:
  - brain_accounting.py  (AccountingMixin)
  - brain_health.py      (HealthChecker)
  - brain_data.py        (DataProvider / get_current_spread)
  - brain_state.py       (DrawdownLadder, ConsecutiveLossTracker, MorningBudget,
                          TokenBucketRateLimiter, TradingState)

Run:  python -m pytest tests/test_brain_mixins.py -v
"""
from __future__ import annotations

import asyncio
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from adaptive_learning import LiveAdaptiveEngine
from neural_governance import NeuralGovernanceEngine
import pytz

sys.path.insert(0, "src")

# ── Pure state-primitive imports (no heavy broker deps) ──────────────────────
from brain_fsm import TradingState
from brain_state import (
    ConsecutiveLossTracker,
    DrawdownLadder,
    DrawdownLevel,
    MorningBudget,
    TokenBucketRateLimiter,
)
from system_types import Position

# ============================================================================
# DB SCHEMA HELPERS
# ============================================================================

_TRADES_DDL = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    instrument TEXT,
    direction TEXT,
    pattern TEXT,
    regime TEXT,
    entry_price REAL,
    exit_price  REAL,
    shares      REAL,
    outcome     TEXT,
    pnl_dollars REAL,
    net_pnl     REAL DEFAULT 0.0,
    broker      TEXT
);
"""

_SYSTEM_STATE_DDL = """
CREATE TABLE IF NOT EXISTS system_state (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _make_memory_db() -> sqlite3.Connection:
    """
    Return a fresh in-memory SQLite connection with the trades table.

    ``check_same_thread=False`` is required because AccountingMixin's
    ``_get_daily_pnl`` runs the DB query inside ``asyncio.to_thread``,
    which dispatches to a worker thread that is different from the thread
    that created the connection.
    """
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.execute(_TRADES_DDL)
    conn.execute(_SYSTEM_STATE_DDL)
    conn.commit()
    return conn


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mem_db():
    """In-memory SQLite database with trades + system_state tables."""
    conn = _make_memory_db()
    yield conn
    conn.close()


@pytest.fixture
def today_ts():
    """ISO timestamp for *today* (UTC)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


@pytest.fixture
def accounting_obj(mem_db):
    """
    A minimal object that has the AccountingMixin methods attached.
    We build it by mixing AccountingMixin directly rather than instantiating
    the heavy TradingBrain, so tests are fast and isolated.
    """
    from brain_accounting import AccountingMixin

    class _Stub(AccountingMixin):
        def __init__(self, conn):
            self.db_conn = conn
            self.ibkr_client = None
            self.ibkr_drawdown = DrawdownLadder(account_type="ibkr", peak_equity=10_000.0)
            self._last_account_value = {"ibkr": 0.0, "mt5": 0.0, "timestamp": 0.0}
            self._account_value_meta = {}
            # Extra attrs required by _update_drawdowns
            self.prop_drawdown = DrawdownLadder(account_type="prop", peak_equity=10_000.0)
            self.positions = []
            self._learned_win_rates = {}
            self.session_stats = {}
            self._background_tasks: set = set()
            self.session_restorer = MagicMock()

    return _Stub(mem_db)


@pytest.fixture
def health_obj():
    """
    Minimal stub for HealthChecker mixin tests.
    Avoids importing TradingBrain or any broker dependencies.
    """
    from brain_health import HealthChecker

    class _Stub(HealthChecker):
        def __init__(self):
            self.positions = []
            self.mode = "paper"
            self.active_broker = "IBKR"
            self.db_conn = None
            self.last_budget_date = datetime.now(timezone.utc)
            self.current_regime = "BULL"
            self._oracle_risk_modifier = 1.0
            self._oracle_dhatu = "Sthiti"
            self.dhatu_oracle = None
            self._is_market_open = lambda: True
            self.last_tick_prices: dict = {}
            self._last_execution_status_notice = 0.0
            self.adaptive_engine = LiveAdaptiveEngine()
            self.governance_engine = NeuralGovernanceEngine()

        def _broker_is_connected(self, conn):
            return True

    return _Stub()


@pytest.fixture
def paper_brain(request):
    """
    Re-use the paper_brain fixture from conftest / test_broker_mock_integration
    by building it inline here (avoids cross-file fixture dependency issues).
    """
    with (
        patch("brain.Vault.get", side_effect=lambda k, d=None: "dummy" if k == "SESSION_SECRET" else (d or "")),
        patch("brain.FORCED_PAPER_MODE", True),
        patch("brain.STARTING_CAPITAL_CAD", 100_000.0),
        patch("brain.SharedIntelligenceBus", MagicMock),
        patch("brain.IBKRConnection", MagicMock),
        patch("agent_c_mt5.MT5Connection", MagicMock),
        patch("brain.LEDGER", MagicMock()),
        patch("brain.PORTFOLIO_ANALYZER", MagicMock()),
        patch("telegram_alerts.send_telegram_alert", new_callable=AsyncMock),
    ):
        from brain import TradingBrain

        brain = TradingBrain(mode="paper")
        brain.ibkr_conn = MagicMock()
        brain.ibkr_conn.is_connected.return_value = False
        brain.ibkr_client = MagicMock()
        brain.ibkr_client.positions.return_value = []
        brain.mt5_conn = MagicMock()
        brain.mt5_conn.is_connected.return_value = False
        brain.is_running = True
        brain.active_broker = "IBKR"
        brain.current_regime = "TRENDING"
        brain.last_budget_date = datetime.now(timezone.utc)
        yield brain


# ============================================================================
# ── brain_accounting.py ──────────────────────────────────────────────────────
# ============================================================================

class TestAccountingMixin:
    """Tests for AccountingMixin._get_daily_pnl and _get_account_value."""

    # ------------------------------------------------------------------
    # test_daily_pnl_returns_zero_for_no_trades
    # ------------------------------------------------------------------
    def test_daily_pnl_returns_zero_for_no_trades(self, accounting_obj):
        """_get_daily_pnl returns 0.0 when there are no trades today."""
        result = asyncio.run(accounting_obj._get_daily_pnl("ibkr"))
        assert result == 0.0, f"Expected 0.0 got {result}"

    # ------------------------------------------------------------------
    # test_daily_pnl_sums_net_pnl_for_today
    # ------------------------------------------------------------------
    def test_daily_pnl_sums_net_pnl_for_today(self, accounting_obj, today_ts, mem_db):
        """_get_daily_pnl uses cost-aware net PnL for today's closed trades."""
        mem_db.executemany(
            "INSERT INTO trades (timestamp, outcome, pnl_dollars, net_pnl, broker) "
            "VALUES (?,?,?,?,?)",
            [
                (today_ts, "WIN", 50.0, 48.0, "ibkr"),
                (today_ts, "LOSS", -20.0, -22.0, "ibkr"),
                (today_ts, "WIN", 30.0, 28.0, "ibkr"),
            ],
        )
        mem_db.commit()

        result = asyncio.run(accounting_obj._get_daily_pnl("ibkr"))
        assert abs(result - 54.0) < 1e-6, f"Expected 54.0 got {result}"

    # ------------------------------------------------------------------
    # test_daily_pnl_ignores_open_trades (pnl_dollars=NULL for OPEN rows)
    # ------------------------------------------------------------------
    def test_daily_pnl_ignores_null_pnl(self, accounting_obj, today_ts, mem_db):
        """
        OPEN trades typically have pnl_dollars=NULL.
        COALESCE(SUM(pnl_dollars), 0) should ignore NULLs.
        """
        mem_db.executemany(
            "INSERT INTO trades (timestamp, outcome, pnl_dollars, broker) VALUES (?,?,?,?)",
            [
                (today_ts, "OPEN", None,  "ibkr"),   # open — no PnL yet
                (today_ts, "WIN",  75.0,  "ibkr"),   # closed win
            ],
        )
        mem_db.commit()

        result = asyncio.run(accounting_obj._get_daily_pnl("ibkr"))
        assert abs(result - 75.0) < 1e-6, f"Expected 75.0 got {result}"

    # ------------------------------------------------------------------
    # test_daily_pnl_filters_by_broker
    # ------------------------------------------------------------------
    def test_daily_pnl_filters_by_broker(self, accounting_obj, today_ts, mem_db):
        """_get_daily_pnl only sums trades for the requested broker."""
        mem_db.executemany(
            "INSERT INTO trades (timestamp, outcome, pnl_dollars, broker) VALUES (?,?,?,?)",
            [
                (today_ts, "WIN",  100.0, "ibkr"),
                (today_ts, "WIN",  999.0, "mt5"),    # different broker — must be excluded
            ],
        )
        mem_db.commit()

        ibkr_pnl = asyncio.run(accounting_obj._get_daily_pnl("ibkr"))
        assert abs(ibkr_pnl - 100.0) < 1e-6, f"Expected 100.0 got {ibkr_pnl}"

        mt5_pnl = asyncio.run(accounting_obj._get_daily_pnl("mt5"))
        assert abs(mt5_pnl - 999.0) < 1e-6, f"Expected 999.0 got {mt5_pnl}"

    # ------------------------------------------------------------------
    # test_daily_pnl_returns_zero_when_db_conn_is_none
    # ------------------------------------------------------------------
    def test_daily_pnl_returns_zero_when_no_db(self, accounting_obj):
        """_get_daily_pnl returns 0.0 gracefully when db_conn is None."""
        accounting_obj.db_conn = None
        result = asyncio.run(accounting_obj._get_daily_pnl("ibkr"))
        assert result == 0.0

    def test_session_pnl_is_rebuilt_from_today_ledger(self, accounting_obj, today_ts, mem_db):
        accounting_obj.active_broker = "IBKR"
        accounting_obj.session_pnl = -999_999.0
        mem_db.executemany(
            "INSERT INTO trades (timestamp, outcome, pnl_dollars, net_pnl, broker) "
            "VALUES (?,?,?,?,?)",
            [
                (today_ts, "WIN", 100.0, 98.0, "ibkr"),
                (today_ts, "LOSS", -50.0, -52.0, "ibkr"),
            ],
        )
        mem_db.commit()

        restored = asyncio.run(accounting_obj._restore_session_pnl_from_ledger())

        assert restored == 46.0
        assert accounting_obj.session_pnl == 46.0

    # ------------------------------------------------------------------
    # test_account_value_fails_closed_when_ibkr_disconnected
    # ------------------------------------------------------------------
    def test_account_value_returns_float_when_ibkr_disconnected(self, accounting_obj):
        """
        An unavailable broker must not present configured capital as live equity.
        """
        accounting_obj.ibkr_client = None
        result = asyncio.run(accounting_obj._get_account_value("ibkr"))
        assert isinstance(result, float)
        assert result == 0.0
        assert accounting_obj._account_value_metadata("ibkr")["authoritative"] is False

    def test_account_value_does_not_recycle_peak_when_broker_cache_is_cold(
        self, accounting_obj
    ):
        account_value = MagicMock(tag="NetLiquidation", currency="USD", value="bad")
        accounting_obj.ibkr_client = MagicMock()
        accounting_obj.ibkr_client.isConnected.return_value = True
        accounting_obj.ibkr_client.accountValues.return_value = [account_value]

        result = asyncio.run(accounting_obj._get_account_value("ibkr", force_fresh=True))

        assert result == 0.0
        assert accounting_obj.ibkr_drawdown.peak_equity == 10_000.0
        assert accounting_obj._account_value_metadata("ibkr")["authoritative"] is False

    def test_account_value_prefers_base_currency_net_liquidation(self, accounting_obj):
        accounting_obj.ibkr_client = MagicMock()
        accounting_obj.ibkr_client.isConnected.return_value = True
        accounting_obj.ibkr_client.accountValues.return_value = [
            MagicMock(tag="NetLiquidation", currency="USD", value="700000"),
            MagicMock(tag="NetLiquidation", currency="BASE", value="950000"),
        ]

        result = asyncio.run(accounting_obj._get_account_value("ibkr", force_fresh=True))

        assert result == 950_000.0
        metadata = accounting_obj._account_value_metadata("ibkr")
        assert metadata["source"] == "ibkr_net_liquidation"
        assert metadata["authoritative"] is True

    # ------------------------------------------------------------------
    # test_account_value_uses_cache_within_60s
    # ------------------------------------------------------------------
    def test_account_value_uses_cache(self, accounting_obj):
        """
        If the cache was populated less than 60 s ago, _get_account_value
        should return the cached value directly.
        """
        accounting_obj._last_account_value["ibkr"] = 12345.0
        accounting_obj._last_account_value["timestamp"] = time.time()  # fresh

        result = asyncio.run(accounting_obj._get_account_value("ibkr"))
        assert abs(result - 12345.0) < 1e-6


# ============================================================================
# ── brain_health.py ──────────────────────────────────────────────────────────
# ============================================================================

class TestHealthChecker:
    """Tests for HealthChecker mixin."""

    # ------------------------------------------------------------------
    # test_pre_market_health_check_passes_in_paper_mode
    # ------------------------------------------------------------------
    def test_pre_market_health_check_passes_in_paper_mode(self, health_obj):
        """
        In paper mode with valid regime + budget date, _pre_market_health_check
        returns (True, 'ALL_CLEAR').
        """
        ok, reason = asyncio.run(health_obj._pre_market_health_check())
        assert ok is True
        assert reason == "ALL_CLEAR"

    # ------------------------------------------------------------------
    # test_health_check_fails_when_regime_unknown
    # ------------------------------------------------------------------
    def test_health_check_fails_when_regime_unknown(self, health_obj):
        """
        If current_regime is UNKNOWN, health check should fail and report it.
        """
        health_obj.current_regime = "UNKNOWN"
        ok, reason = asyncio.run(health_obj._pre_market_health_check())
        assert ok is False
        assert "regime" in reason.lower()

    # ------------------------------------------------------------------
    # test_health_check_fails_when_budget_not_set
    # ------------------------------------------------------------------
    def test_health_check_fails_when_budget_not_set(self, health_obj):
        """
        If last_budget_date is None, health check should fail with budget message.
        """
        health_obj.last_budget_date = None
        ok, reason = asyncio.run(health_obj._pre_market_health_check())
        assert ok is False
        assert "budget" in reason.lower()

    # ------------------------------------------------------------------
    # test_health_check_prunes_corrupt_positions
    # ------------------------------------------------------------------
    def test_health_check_prunes_corrupt_positions(self, health_obj):
        """
        Positions with invalid entry_price/qty/stop_loss are pruned rather
        than causing a hard failure.
        """
        bad_pos = Position(
            symbol="BADTICKER",
            qty=0.0,          # Invalid qty
            entry_price=-1.0, # Invalid price
            stop_loss=0.0,    # Invalid stop
            entry_time=datetime.now(timezone.utc),
        )
        health_obj.positions = [bad_pos]

        ok, _ = asyncio.run(health_obj._pre_market_health_check())
        # The corrupt position should be pruned — no crash, and positions list cleaned
        assert len(health_obj.positions) == 0

    # ------------------------------------------------------------------
    # test_health_check_with_db_conn_none_does_not_crash
    # ------------------------------------------------------------------
    def test_health_check_with_db_conn_none_does_not_crash(self, health_obj):
        """
        Setting db_conn = None should not raise; DB check is simply skipped.
        """
        health_obj.db_conn = None
        try:
            ok, reason = asyncio.run(health_obj._pre_market_health_check())
        except Exception as exc:
            pytest.fail(f"_pre_market_health_check raised unexpectedly: {exc}")

    # ------------------------------------------------------------------
    # test_decay_risk_modifier_no_oracle_is_noop
    # ------------------------------------------------------------------
    def test_decay_risk_modifier_no_oracle_is_noop(self, health_obj):
        """
        When dhatu_oracle is None, _decay_risk_modifier should silently return.
        """
        health_obj.dhatu_oracle = None
        health_obj._oracle_risk_modifier = 1.5
        asyncio.run(health_obj._decay_risk_modifier())
        # Value should remain unchanged (no oracle to decay towards)
        assert health_obj._oracle_risk_modifier == 1.5

    # ------------------------------------------------------------------
    # test_decay_risk_modifier_moves_toward_baseline
    # ------------------------------------------------------------------
    def test_decay_risk_modifier_moves_toward_baseline(self, health_obj):
        """
        When an oracle is present, _decay_risk_modifier should nudge the
        modifier toward the oracle's baseline value.
        """
        mock_state = MagicMock()
        mock_state.risk_modifier = 1.0
        mock_oracle = MagicMock()
        mock_oracle.get_current_state.return_value = mock_state

        health_obj.dhatu_oracle = mock_oracle
        health_obj._oracle_risk_modifier = 1.5   # 0.5 above baseline

        asyncio.run(health_obj._decay_risk_modifier())

        # After one step the modifier should be closer to 1.0 (but not there yet)
        assert health_obj._oracle_risk_modifier < 1.5


# ============================================================================
# ── brain_data.py — get_current_spread ──────────────────────────────────────
# ============================================================================

class TestDataProvider:
    """
    Tests for DataProvider / brain.get_current_spread.
    These use the paper_brain fixture (full TradingBrain) to exercise real code paths.
    """

    # ------------------------------------------------------------------
    # test_get_current_spread_returns_dict_with_required_keys
    # ------------------------------------------------------------------
    def test_get_current_spread_returns_dict_with_required_keys(self, paper_brain):
        """get_current_spread always returns a dict with bid/ask/spread/mid keys."""
        result = asyncio.run(paper_brain.get_current_spread("AAPL"))
        assert isinstance(result, dict)
        for key in ("bid", "ask", "spread", "mid"):
            assert key in result, f"Missing key: {key}"

    # ------------------------------------------------------------------
    # test_get_current_spread_zeros_when_no_tick_data
    # ------------------------------------------------------------------
    def test_get_current_spread_zeros_when_no_tick_data(self, paper_brain):
        """
        When no tick data has been received for a symbol, spread values
        should all be 0.0 (safe default).
        """
        paper_brain.last_tick_prices.clear()
        paper_brain.last_tick_bids.clear()
        paper_brain.last_tick_asks.clear()

        result = asyncio.run(paper_brain.get_current_spread("UNKNOWN_SYM"))
        assert result["spread"] == 0.0
        assert result["bid"] == 0.0

    # ------------------------------------------------------------------
    # test_get_current_spread_reflects_tick_data
    # ------------------------------------------------------------------
    def test_get_current_spread_reflects_tick_data(self, paper_brain):
        """
        After calling on_tick with explicit bid/ask, get_current_spread
        returns the correct non-zero spread.
        """
        asyncio.run(
            paper_brain.on_tick(
                {"symbol": "SPY", "price": 500.0, "bid": 499.95, "ask": 500.05}
            )
        )

        result = asyncio.run(paper_brain.get_current_spread("SPY"))
        assert result["bid"] == pytest.approx(499.95)
        assert result["ask"] == pytest.approx(500.05)
        assert result["spread"] == pytest.approx(0.10, abs=1e-6)
        assert result["mid"] == pytest.approx(500.0)

    # ------------------------------------------------------------------
    # test_detect_regime_returns_valid_string
    # ------------------------------------------------------------------
    def test_detect_regime_returns_valid_string(self, paper_brain):
        """
        _detect_regime must return one of the five recognised regime strings.
        All external DB/data calls are mocked to avoid IO.
        """
        valid_regimes = {"BULL", "BEAR", "VOLATILE", "CHOPPY", "TRENDING"}

        # Mock _get_vix to return a stable, low VIX
        paper_brain._get_vix = AsyncMock(return_value=15.0)
        # Mock regime_classifier.classify directly
        paper_brain.regime_classifier = MagicMock()
        paper_brain.regime_classifier.classify.return_value = "BULL"
        # Mock session_restorer so capsule save doesn't fail
        paper_brain.session_restorer = MagicMock()
        paper_brain.session_restorer.save_cognitive_capsule = MagicMock()

        regime = asyncio.run(paper_brain._detect_regime())
        assert regime in valid_regimes, f"Unexpected regime: {regime}"

    # ------------------------------------------------------------------
    # test_detect_regime_handles_vix_failure_gracefully
    # ------------------------------------------------------------------
    def test_detect_regime_handles_vix_failure_gracefully(self, paper_brain):
        """
        If _get_vix raises an exception, _detect_regime must not crash —
        it should return a fallback regime string.
        """
        valid_regimes = {"BULL", "BEAR", "VOLATILE", "CHOPPY", "TRENDING"}

        async def _raise(*a, **kw):
            raise RuntimeError("VIX data unavailable")

        paper_brain._get_vix = _raise
        paper_brain.session_restorer = MagicMock()
        paper_brain.session_restorer.save_cognitive_capsule = MagicMock()

        regime = asyncio.run(paper_brain._detect_regime())
        assert regime in valid_regimes, f"Unexpected regime after VIX failure: {regime}"

    # ------------------------------------------------------------------
    # test_fetch_market_snapshot_returns_dict_with_price_key
    # ------------------------------------------------------------------
    def test_fetch_market_snapshot_returns_dict_with_price_key(self, paper_brain):
        """
        _fetch_market_snapshot returns a dict with at least a 'price' key.
        We seed the last_tick_prices so no DB is needed.
        """
        paper_brain.last_tick_prices["AAPL"] = 185.0
        paper_brain._get_vix = AsyncMock(return_value=18.0)

        snapshot = asyncio.run(paper_brain._fetch_market_snapshot("AAPL"))
        assert snapshot is not None
        assert "price" in snapshot
        assert snapshot["price"] == pytest.approx(185.0)

    # ------------------------------------------------------------------
    # test_get_vix_returns_default_when_db_is_none
    # ------------------------------------------------------------------
    def test_get_vix_returns_default_when_db_is_none(self, paper_brain):
        """_get_vix falls back to 18.0 when db_conn is None and no cache."""
        paper_brain.db_conn = None
        paper_brain._last_vix = 18.0   # canonical fallback

        vix = asyncio.run(paper_brain._get_vix())
        assert isinstance(vix, float)
        assert vix > 0


# ============================================================================
# ── brain_state.py — DrawdownLadder ─────────────────────────────────────────
# ============================================================================

class TestDrawdownLadder:
    """Tests for DrawdownLadder state machine."""

    def test_initial_level_is_normal(self):
        ladder = DrawdownLadder(account_type="ibkr", peak_equity=10_000.0)
        assert ladder.level == DrawdownLevel.NORMAL

    def test_update_no_drawdown_stays_normal(self):
        ladder = DrawdownLadder(account_type="ibkr", peak_equity=10_000.0)
        with patch("trading_state.TradingStateManager"):
            level = ladder.update(10_000.0)
        assert level == DrawdownLevel.NORMAL

    def test_update_escalates_to_yellow(self):
        """
        YELLOW threshold for IBKR is 12% drawdown.
        $10,000 * (1 - 0.13) = $8,700 → triggers YELLOW.
        """
        with patch("trading_state.TradingStateManager"):
            ladder = DrawdownLadder(account_type="ibkr", peak_equity=10_000.0)
            ladder.update(10_000.0)  # Calibrate peak
            level = ladder.update(8_700.0)  # 13% drawdown (> 12% YELLOW threshold)
        assert level == DrawdownLevel.YELLOW

    def test_peak_equity_updates_on_new_high(self):
        with patch("trading_state.TradingStateManager"):
            ladder = DrawdownLadder(account_type="ibkr", peak_equity=10_000.0)
            ladder.update(11_000.0)  # New high
        assert ladder.peak_equity == 11_000.0

    def test_get_size_modifier_normal_is_one(self):
        ladder = DrawdownLadder(account_type="ibkr", peak_equity=10_000.0)
        assert ladder.get_size_modifier() == 1.0

    def test_is_trading_allowed_circuit_breaker_false(self):
        ladder = DrawdownLadder(account_type="ibkr")
        ladder.level = DrawdownLevel.CIRCUIT_BREAKER
        assert ladder.is_trading_allowed() is False

    @pytest.mark.asyncio
    async def test_red_zone_alert_completes_on_running_loop(self):
        alert = AsyncMock()
        with (
            patch("telegram_alerts.send_telegram_alert", alert),
            patch("trading_state.TradingStateManager") as state_manager,
        ):
            ladder = DrawdownLadder(account_type="ibkr", peak_equity=10_000.0)
            level = ladder.update(7_400.0)
            await asyncio.sleep(0)

        assert level == DrawdownLevel.RED
        state_manager.halt.assert_called_once()
        alert.assert_awaited_once()


# ============================================================================
# ── brain_state.py — ConsecutiveLossTracker ──────────────────────────────────
# ============================================================================

class TestConsecutiveLossTracker:
    """Tests for the graduated consecutive-loss response system."""

    def test_initial_state(self):
        tracker = ConsecutiveLossTracker()
        assert tracker.consecutive_losses == 0
        assert tracker.win_streak == 0
        assert tracker.paper_mode_forced is False

    def test_win_resets_losses(self):
        tracker = ConsecutiveLossTracker()
        tracker.record_outcome(is_win=False)
        tracker.record_outcome(is_win=False)
        tracker.record_outcome(is_win=True)
        assert tracker.consecutive_losses == 0
        assert tracker.win_streak == 1

    def test_two_losses_gives_50_pct_modifier(self):
        tracker = ConsecutiveLossTracker()
        tracker.record_outcome(is_win=False)
        tracker.record_outcome(is_win=False)
        assert tracker.get_size_modifier() == pytest.approx(0.50)

    def test_three_losses_enters_reduce_only(self):
        tracker = ConsecutiveLossTracker()
        for _ in range(3):
            tracker.record_outcome(is_win=False)
        assert tracker.reduce_only is True
        assert tracker.is_trading_allowed() is False
        assert tracker.get_size_modifier() == pytest.approx(0.0)
        assert tracker.pause_until is not None

    def test_four_losses_forces_paper_mode(self):
        tracker = ConsecutiveLossTracker()
        for _ in range(4):
            tracker.record_outcome(is_win=False)
        assert tracker.paper_mode_forced is True
        assert tracker.reduce_only is True
        assert tracker.is_trading_allowed() is False

    def test_five_losses_sets_audit_required(self):
        tracker = ConsecutiveLossTracker()
        for _ in range(5):
            tracker.record_outcome(is_win=False)
        assert tracker.audit_required is True

    def test_win_streak_capped_at_1_15x(self):
        """Win-streak compounding must be capped at 1.15x (AGENTS.md note #6)."""
        tracker = ConsecutiveLossTracker()
        for _ in range(10):   # Long win streak
            tracker.record_outcome(is_win=True)
        modifier = tracker.get_size_modifier()
        assert modifier <= 1.15, f"Win-streak modifier exceeded cap: {modifier}"

    def test_is_trading_allowed_respects_pause(self):
        tracker = ConsecutiveLossTracker()
        # Force pause in the future
        tracker.pause_until = datetime.now(timezone.utc) + timedelta(hours=1)
        assert tracker.is_trading_allowed() is False

    def test_is_trading_allowed_after_pause_expires(self):
        tracker = ConsecutiveLossTracker()
        tracker.pause_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        assert tracker.is_trading_allowed() is True

    def test_three_loss_recovery_checkpoint_is_next_regular_session(self):
        tracker = ConsecutiveLossTracker()
        now = datetime(2026, 6, 3, 14, 0, tzinfo=timezone.utc)
        recovery = tracker._next_regular_session_recovery_time(now)
        assert recovery > now
        assert recovery.astimezone(pytz.timezone("US/Eastern")).hour == 9
        assert recovery.astimezone(pytz.timezone("US/Eastern")).minute == 45


# ============================================================================
# ── brain_state.py — MorningBudget ───────────────────────────────────────────
# ============================================================================

class TestMorningBudget:
    """Tests for the daily risk budget generator."""

    def test_generate_bull_regime(self):
        budget = MorningBudget()
        budget.generate(
            regime="BULL",
            consecutive_losses=0,
            dd_level=DrawdownLevel.NORMAL,
        )
        assert budget.regime == "BULL"
        assert budget.max_trades > 0
        assert budget.generated_at is not None

    def test_generate_bear_regime_is_more_conservative(self):
        bull = MorningBudget()
        bull.generate("BULL", 0, DrawdownLevel.NORMAL)

        bear = MorningBudget()
        bear.generate("BEAR", 0, DrawdownLevel.NORMAL)

        # BEAR should have fewer max_trades and higher min_catalyst
        assert bear.max_trades <= bull.max_trades
        assert bear.min_catalyst >= bull.min_catalyst

    def test_orange_drawdown_blocks_trades(self):
        budget = MorningBudget()
        budget.generate(
            regime="BULL",
            consecutive_losses=0,
            dd_level=DrawdownLevel.ORANGE,
        )
        assert budget.max_trades == 0

    def test_two_consecutive_losses_raises_catalyst_bar(self):
        clean = MorningBudget()
        clean.generate("BULL", consecutive_losses=0, dd_level=DrawdownLevel.NORMAL)

        stressed = MorningBudget()
        stressed.generate("BULL", consecutive_losses=2, dd_level=DrawdownLevel.NORMAL)

        assert stressed.min_catalyst >= clean.min_catalyst

    def test_unknown_regime_falls_back_to_choppy_config(self):
        budget = MorningBudget()
        budget.generate("UNKNOWN_REGIME", 0, DrawdownLevel.NORMAL)
        # Should not crash and should produce sensible defaults
        assert budget.max_trades >= 0
        assert budget.min_catalyst > 0


# ============================================================================
# ── brain_state.py — TradingState FSM ────────────────────────────────────────
# ============================================================================

class TestTradingStateFSM:
    """Tests for TradingState enum + TradingBrain state transitions."""

    def test_initial_state_is_standby(self, paper_brain):
        """
        Freshly created TradingBrain must start in STANDBY (test requirement).
        """
        assert paper_brain.state == TradingState.STANDBY

    def test_transition_standby_to_positioned(self, paper_brain):
        """
        The FSM must accept STANDBY -> POSITIONED transition without error.
        """
        asyncio.run(paper_brain.transition_to(TradingState.POSITIONED))
        assert paper_brain.state == TradingState.POSITIONED

    def test_redundant_transition_is_noop(self, paper_brain):
        """Transitioning to the current state should be a no-op (no error)."""
        asyncio.run(paper_brain.transition_to(TradingState.STANDBY))
        assert paper_brain.state == TradingState.STANDBY

    def test_state_standby_is_not_positioned(self, paper_brain):
        assert paper_brain.state != TradingState.POSITIONED

    def test_position_count_matches_positions_list(self, paper_brain):
        """
        len(brain.positions) must stay in sync after adding a mock position.
        """
        assert len(paper_brain.positions) == 0

        mock_pos = Position(
            symbol="TSLA",
            qty=10,
            entry_price=200.0,
            stop_loss=190.0,
            entry_time=datetime.now(timezone.utc),
        )
        paper_brain.positions.append(mock_pos)
        assert len(paper_brain.positions) == 1

    def test_brain_state_can_be_serialized(self, paper_brain):
        """
        State snapshot dict must be serialisable to a plain Python dict.
        The test verifies no exceptions are raised during the dump.
        """
        snapshot = {
            "state": paper_brain.state.name,
            "regime": paper_brain.current_regime,
            "positions": len(paper_brain.positions),
            "mode": paper_brain.mode,
        }
        import json

        try:
            dumped = json.dumps(snapshot)
            parsed = json.loads(dumped)
        except Exception as exc:
            pytest.fail(f"State serialization raised: {exc}")

        assert parsed["state"] == "STANDBY"
        assert isinstance(parsed["positions"], int)


# ============================================================================
# ── brain_state.py — TokenBucketRateLimiter ──────────────────────────────────
# ============================================================================

class TestTokenBucketRateLimiter:
    """Tests for the async token-bucket rate limiter."""

    def test_acquire_single_token_succeeds(self):
        limiter = TokenBucketRateLimiter(rate=100.0, capacity=10)

        async def _run():
            await limiter.acquire()

        asyncio.run(_run())  # Should complete without blocking

    def test_tokens_decrease_after_acquire(self):
        limiter = TokenBucketRateLimiter(rate=100.0, capacity=10)

        async def _run():
            before = limiter.tokens
            await limiter.acquire()
            after = limiter.tokens
            return before, after

        before, after = asyncio.run(_run())
        assert after < before
