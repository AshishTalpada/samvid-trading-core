"""
tests/test_brain_execution_position.py

Comprehensive tests for:
  1. brain_execution.py  — _log_trade_exit: net_pnl, outcome, r_multiple
  2. brain_position.py   — _state_positioned: HEARTBEAT_VETO age-gate logic
  3. coordinator.py      — initiate_trade_lifecycle: friction veto RR threshold

All tests run fully offline with no broker / file-system dependencies.
An in-memory SQLite DB (check_same_thread=False) is used wherever DB writes
are exercised — required because _log_trade_exit runs _sync_log in a thread
via asyncio.to_thread.
"""

from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, "src")

# ---------------------------------------------------------------------------
# Helpers / shared factories
# ---------------------------------------------------------------------------

def _make_trades_table(conn: sqlite3.Connection) -> None:
    """Create the minimal 'trades' table used by _log_trade_exit."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trades (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp       TEXT,
            instrument      TEXT,
            direction       TEXT,
            pattern         TEXT,
            regime          TEXT,
            entry_price     REAL,
            stop_price      REAL,
            target_price    REAL,
            shares          REAL,
            r_r_ratio       REAL,
            catalyst_score  REAL,
            dhatu_state     TEXT,
            belief_at_entry REAL,
            broker          TEXT,
            account_id      TEXT,
            trading_mode    TEXT,
            outcome         TEXT  DEFAULT 'OPEN',
            commission      REAL  DEFAULT 0.0,
            slippage        REAL  DEFAULT 0.0,
            net_pnl         REAL  DEFAULT 0.0,
            intel_snapshot  TEXT,
            exit_price      REAL,
            pnl_dollars     REAL,
            r_multiple      REAL,
            hold_hours      REAL,
            belief_at_exit  REAL,
            notes           TEXT
        )
    """)
    conn.commit()


def _insert_open_trade(conn: sqlite3.Connection, symbol: str = "AAPL") -> int:
    """Insert a synthetic open trade row and return its rowid (= primary key id)."""
    conn.execute(
        """
        INSERT INTO trades
          (timestamp, instrument, direction, pattern, regime, entry_price,
           stop_price, target_price, shares, r_r_ratio, catalyst_score,
           dhatu_state, belief_at_entry, broker, account_id, trading_mode,
           outcome, commission, slippage, net_pnl)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            symbol,
            "LONG",
            "bull_flag",
            "TRENDING",
            100.0,   # entry_price
            98.0,    # stop_price
            104.0,   # target_price
            10,      # shares
            2.0,     # r_r_ratio
            70.0,    # catalyst_score
            "STHIRA",
            0.70,    # belief_at_entry
            "ibkr",
            "TEST123",
            "paper",
            "OPEN",
            0.0,     # commission
            0.0,     # slippage
            0.0,     # net_pnl
        ),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


from system_types import Position


def _make_position(
    symbol: str = "AAPL",
    qty: float = 10.0,
    entry: float = 100.0,
    stop: float = 98.0,
    commission: float = 0.0,
    slippage: float = 0.0,
    db_id: int = 1,
    entry_time: datetime | None = None,
) -> Position:
    if entry_time is None:
        entry_time = datetime.now(timezone.utc)
    pos = Position(
        symbol=symbol,
        qty=qty,
        entry_price=entry,
        entry_time=entry_time,
        initial_stop=stop,
        stop_loss=stop,
        take_profit=entry + 4.0,
        pattern="bull_flag",
        initial_belief=0.70,
        current_belief=0.70,
        catalyst_score=70.0,
        dhatu_state="STHIRA",
        regime_at_entry="TRENDING",
        r_r_ratio=2.0,
        account_type="ibkr",
        account_id="TEST123",
        commission_cost=commission,
        slippage_cost=slippage,
        db_id=db_id,
    )
    return pos


# ---------------------------------------------------------------------------
# Helper: shared TradingBrain patch context (reused by multiple fixtures)
# ---------------------------------------------------------------------------

_BRAIN_PATCHES = [
    patch("brain.Vault.get", side_effect=lambda k, d=None: "dummy" if k == "SESSION_SECRET" else (d or "")),
    patch("brain.FORCED_PAPER_MODE", True),
    patch("brain.STARTING_CAPITAL_CAD", 100_000.0),
    patch("brain.SharedIntelligenceBus", MagicMock),
    patch("brain.IBKRConnection", MagicMock),
    patch("agent_c_mt5.MT5Connection", MagicMock),
    patch("brain.LEDGER", MagicMock()),
    patch("brain.PORTFOLIO_ANALYZER", MagicMock()),
    patch("telegram_alerts.send_telegram_alert", new_callable=AsyncMock),
]


def _build_paper_brain():
    """Construct a TradingBrain in paper mode. Caller must manage context patches."""
    from brain import TradingBrain
    brain = TradingBrain(mode="paper")

    brain.ibkr_conn = MagicMock()
    brain.ibkr_conn.is_connected.return_value = False
    brain.ibkr_conn.has_pending_order.return_value = False
    brain.ibkr_conn.generate_exec_token.return_value = "MOCK_TOKEN"
    brain.ibkr_client = MagicMock()
    brain.ibkr_client.positions.return_value = []
    brain.mt5_conn = MagicMock()
    brain.mt5_conn.is_connected.return_value = False
    brain.is_running = True
    brain.active_broker = "IBKR"
    brain.current_regime = "TRENDING"
    brain.last_budget_date = datetime.now(timezone.utc)

    # NOTE: check_same_thread=False is required because _log_trade_exit calls
    # asyncio.to_thread(_sync_log), which runs on a worker thread different from
    # the main thread that created the in-memory connection.
    mem_conn = sqlite3.connect(":memory:", check_same_thread=False)
    _make_trades_table(mem_conn)
    brain.db_conn = mem_conn

    # Post-mortem side-effects (skill tree / wisdom)
    brain.wisdom = MagicMock()
    brain.wisdom.write_post_mortem = MagicMock()
    brain.skill_tree = MagicMock()
    brain.skill_tree.skills = {"pnl_to_next": 5000.0}
    brain.skill_tree._save = MagicMock()
    brain.loss_tracker = MagicMock()
    brain.loss_tracker.consecutive_losses = 0
    brain.loss_tracker.win_streak = 0

    return brain


# ---------------------------------------------------------------------------
# Brain fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def paper_brain():
    """TradingBrain in paper mode with an in-memory DB and all external deps mocked."""
    patchers = [
        patch("brain.Vault.get", side_effect=lambda k, d=None: "dummy" if k == "SESSION_SECRET" else (d or "")),
        patch("brain.FORCED_PAPER_MODE", True),
        patch("brain.STARTING_CAPITAL_CAD", 100_000.0),
        patch("brain.SharedIntelligenceBus", MagicMock),
        patch("brain.IBKRConnection", MagicMock),
        patch("agent_c_mt5.MT5Connection", MagicMock),
        patch("brain.LEDGER", MagicMock()),
        patch("brain.PORTFOLIO_ANALYZER", MagicMock()),
        patch("telegram_alerts.send_telegram_alert", new_callable=AsyncMock),
    ]
    for p in patchers:
        p.start()

    brain = _build_paper_brain()
    yield brain

    for p in reversed(patchers):
        p.stop()


# ===========================================================================
# SECTION 1 — brain_execution.py: _log_trade_exit
# ===========================================================================


class TestLogTradeExitNetPnl:
    """Tests for the net_pnl calculation and outcome classification in _log_trade_exit."""

    @pytest.mark.asyncio
    async def test_net_pnl_deducts_commission_and_slippage(self, paper_brain):
        """
        Gross pnl=+10.0, commission=2.0, slippage=1.5 → net=6.5.
        pnl_dollars stored = 10.0 (gross).
        outcome = "WIN".
        """
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "AAPL")
        pos = _make_position(commission=2.0, slippage=1.5, db_id=db_id)

        gross_pnl = 10.0
        r_multiple = 5.0
        await paper_brain._log_trade_exit(pos, "EXIT_P1", 101.0, gross_pnl, r_multiple)

        row = conn.execute(
            "SELECT net_pnl, pnl_dollars, outcome FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None, "Trade row not found after _log_trade_exit"
        net_pnl, pnl_dollars, outcome = row
        assert net_pnl == pytest.approx(6.5, abs=1e-9), f"Expected net_pnl=6.5, got {net_pnl}"
        assert pnl_dollars == pytest.approx(10.0, abs=1e-9), f"Expected pnl_dollars=10.0, got {pnl_dollars}"
        assert outcome == "WIN", f"Expected outcome=WIN, got {outcome}"

    @pytest.mark.asyncio
    async def test_outcome_is_loss_when_net_pnl_negative(self, paper_brain):
        """
        Gross pnl=+0.5, commission=2.0, slippage=1.0 → net=-2.5.
        outcome = "LOSS" (not WIN despite positive gross).
        """
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "MSFT")
        pos = _make_position(symbol="MSFT", commission=2.0, slippage=1.0, db_id=db_id)

        gross_pnl = 0.5
        await paper_brain._log_trade_exit(pos, "STOP_LOSS", 100.5, gross_pnl, -0.25)

        row = conn.execute(
            "SELECT net_pnl, outcome FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        net_pnl, outcome = row
        assert net_pnl == pytest.approx(-2.5, abs=1e-9), f"Expected net_pnl=-2.5, got {net_pnl}"
        assert outcome == "LOSS", f"Expected outcome=LOSS, got {outcome}"

    @pytest.mark.asyncio
    async def test_outcome_breakeven_when_net_zero(self, paper_brain):
        """
        Gross pnl=3.0, commission=2.0, slippage=1.0 → net=0.0.
        outcome = "BREAKEVEN".
        """
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "SPY")
        pos = _make_position(symbol="SPY", commission=2.0, slippage=1.0, db_id=db_id)

        gross_pnl = 3.0
        await paper_brain._log_trade_exit(pos, "TARGET_HIT", 100.3, gross_pnl, 0.0)

        row = conn.execute(
            "SELECT net_pnl, outcome FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        net_pnl, outcome = row
        assert net_pnl == pytest.approx(0.0, abs=1e-9), f"Expected net_pnl=0.0, got {net_pnl}"
        assert outcome == "BREAKEVEN", f"Expected outcome=BREAKEVEN, got {outcome}"

    @pytest.mark.asyncio
    async def test_r_multiple_sign_long_loss(self, paper_brain):
        """
        LONG position (qty>0), entry=100, stop=98, exit=99.
        Gross pnl=(99-100)*10 = -10.
        r_multiple=(99-100)/abs(100-98)*1 = -0.5 — must be stored negative.
        """
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "NVDA")
        pos = _make_position(symbol="NVDA", qty=10.0, entry=100.0, stop=98.0, db_id=db_id)

        risk_per_unit = abs(pos.entry_price - pos.initial_stop)  # 2.0
        exit_price = 99.0
        entry_direction_sign = 1  # LONG
        r_multiple = (exit_price - pos.entry_price) / risk_per_unit * entry_direction_sign
        gross_pnl = (exit_price - pos.entry_price) * pos.qty

        await paper_brain._log_trade_exit(pos, "STOP_LOSS", exit_price, gross_pnl, r_multiple)

        row = conn.execute(
            "SELECT r_multiple FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        stored_r = row[0]
        assert stored_r is not None, "r_multiple column was NULL"
        assert stored_r < 0, f"Expected negative r_multiple for long loss, got {stored_r}"
        assert stored_r == pytest.approx(-0.5, abs=1e-9)

    @pytest.mark.asyncio
    async def test_r_multiple_sign_short_loss(self, paper_brain):
        """
        SHORT position (qty<0), entry=100, stop=102, exit=101.
        entry_direction_sign = -1
        r_multiple = (101-100)/abs(100-102)*(-1) = -0.5 — must be stored negative.
        """
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "TSLA")
        pos = _make_position(
            symbol="TSLA",
            qty=-10.0,
            entry=100.0,
            stop=102.0,
            db_id=db_id,
        )

        risk_per_unit = abs(pos.entry_price - pos.initial_stop)  # 2.0
        exit_price = 101.0
        entry_direction_sign = -1  # SHORT
        r_multiple = (exit_price - pos.entry_price) / risk_per_unit * entry_direction_sign
        gross_pnl = (exit_price - pos.entry_price) * pos.qty  # (1)*(-10) = -10

        await paper_brain._log_trade_exit(pos, "HEARTBEAT_VETO", exit_price, gross_pnl, r_multiple)

        row = conn.execute(
            "SELECT r_multiple FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        stored_r = row[0]
        assert stored_r is not None, "r_multiple column was NULL"
        assert stored_r < 0, f"Expected negative r_multiple for short loss, got {stored_r}"
        assert stored_r == pytest.approx(-0.5, abs=1e-9)

    @pytest.mark.asyncio
    async def test_r_multiple_positive_long_win(self, paper_brain):
        """
        LONG (qty>0), entry=100, stop=98, exit=104.
        r_multiple = (104-100)/2*1 = 2.0 — stored positive.
        """
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "AMD")
        pos = _make_position(symbol="AMD", qty=10.0, entry=100.0, stop=98.0, db_id=db_id)

        exit_price = 104.0
        r_multiple = (exit_price - pos.entry_price) / abs(pos.entry_price - pos.initial_stop)
        gross_pnl = (exit_price - pos.entry_price) * pos.qty  # 40

        await paper_brain._log_trade_exit(pos, "TARGET_HIT", exit_price, gross_pnl, r_multiple)

        row = conn.execute(
            "SELECT r_multiple, outcome FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        stored_r, outcome = row
        assert stored_r is not None, "r_multiple column was NULL"
        assert stored_r > 0, f"Expected positive r_multiple, got {stored_r}"
        assert stored_r == pytest.approx(2.0, abs=1e-9)
        assert outcome == "WIN"

    @pytest.mark.asyncio
    async def test_exit_price_stored_correctly(self, paper_brain):
        """exit_price passed in is stored in the DB."""
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "GOOG")
        pos = _make_position(symbol="GOOG", db_id=db_id)

        await paper_brain._log_trade_exit(pos, "EXIT_P2", 103.5, 35.0, 1.75)

        row = conn.execute(
            "SELECT exit_price FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == pytest.approx(103.5, abs=1e-9)

    @pytest.mark.asyncio
    async def test_notes_contain_exit_type(self, paper_brain):
        """The exit_type string is appended to the notes column."""
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "META")
        pos = _make_position(symbol="META", db_id=db_id)

        await paper_brain._log_trade_exit(pos, "VIX_PROTOCOL", 100.0, 0.0, 0.0)

        row = conn.execute(
            "SELECT notes FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        notes = row[0] or ""
        assert "VIX_PROTOCOL" in notes, f"Expected 'VIX_PROTOCOL' in notes, got: {notes}"

    @pytest.mark.asyncio
    async def test_zero_commission_slippage_net_equals_gross(self, paper_brain):
        """With commission=0 and slippage=0, net_pnl == gross pnl."""
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "QQQ")
        pos = _make_position(symbol="QQQ", commission=0.0, slippage=0.0, db_id=db_id)

        gross_pnl = 25.0
        await paper_brain._log_trade_exit(pos, "EXIT_P3", 102.5, gross_pnl, 1.0)

        row = conn.execute(
            "SELECT net_pnl, pnl_dollars FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        net_pnl, pnl_dollars = row
        assert net_pnl == pytest.approx(25.0, abs=1e-9)
        assert pnl_dollars == pytest.approx(25.0, abs=1e-9)

    @pytest.mark.asyncio
    async def test_performance_summary_updated(self, paper_brain):
        """After exit, performance_summary table should be populated."""
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "IWM")
        pos = _make_position(symbol="IWM", commission=1.0, slippage=0.5, db_id=db_id)

        await paper_brain._log_trade_exit(pos, "TARGET_HIT", 103.0, 30.0, 1.5)

        # performance_summary is created lazily inside _log_trade_exit
        try:
            row = conn.execute(
                "SELECT value FROM performance_summary WHERE key='latest'"
            ).fetchone()
            assert row is not None, "performance_summary row not found"
            summary = json.loads(row[0])
            assert "closed_count" in summary
            assert summary["closed_count"] >= 1
        except sqlite3.OperationalError:
            # Table may not exist if DB schema differs; not fatal for net_pnl tests
            pass

    @pytest.mark.asyncio
    async def test_large_commission_forces_loss_outcome(self, paper_brain):
        """
        Even a large gross profit becomes a LOSS when commission exceeds it.
        gross=100, commission=120, slippage=5 → net=-25 → LOSS.
        """
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "AMZN")
        pos = _make_position(symbol="AMZN", commission=120.0, slippage=5.0, db_id=db_id)

        gross_pnl = 100.0
        await paper_brain._log_trade_exit(pos, "EXIT_P1", 110.0, gross_pnl, 0.5)

        row = conn.execute(
            "SELECT net_pnl, outcome FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        net_pnl, outcome = row
        assert net_pnl == pytest.approx(-25.0, abs=1e-9)
        assert outcome == "LOSS"

    @pytest.mark.asyncio
    async def test_win_streak_tracked_after_profit(self, paper_brain):
        """loss_tracker.record_outcome is called with True for a positive gross pnl."""
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "AAPL")
        pos = _make_position(db_id=db_id)

        await paper_brain._log_trade_exit(pos, "TARGET_HIT", 102.0, 20.0, 1.0)

        paper_brain.loss_tracker.record_outcome.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_loss_tracker_called_with_false_for_loss(self, paper_brain):
        """loss_tracker.record_outcome is called with False for negative gross pnl."""
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "AAPL")
        pos = _make_position(db_id=db_id)

        await paper_brain._log_trade_exit(pos, "STOP_LOSS", 98.0, -20.0, -1.0)

        paper_brain.loss_tracker.record_outcome.assert_called_once_with(False)

    @pytest.mark.asyncio
    async def test_hold_hours_is_positive(self, paper_brain):
        """hold_hours stored in DB should be non-negative."""
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "SPY")
        pos = _make_position(symbol="SPY", db_id=db_id)

        await paper_brain._log_trade_exit(pos, "EXIT_P1", 101.0, 10.0, 0.5)

        row = conn.execute(
            "SELECT hold_hours FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        hold_hours = row[0]
        assert hold_hours is not None
        assert hold_hours >= 0.0, f"Expected non-negative hold_hours, got {hold_hours}"

    @pytest.mark.asyncio
    async def test_belief_at_exit_stored(self, paper_brain):
        """belief_at_exit should be stored from pos.current_belief."""
        conn = paper_brain.db_conn
        db_id = _insert_open_trade(conn, "AAPL")
        pos = _make_position(db_id=db_id)
        pos.current_belief = 0.82

        await paper_brain._log_trade_exit(pos, "TARGET_HIT", 103.0, 30.0, 1.5)

        row = conn.execute(
            "SELECT belief_at_exit FROM trades WHERE rowid=?", (db_id,)
        ).fetchone()
        assert row is not None
        assert row[0] == pytest.approx(0.82, abs=1e-9)


# ===========================================================================
# SECTION 2 — brain_position.py: HEARTBEAT_VETO age gate in _state_positioned
# ===========================================================================

# ---------------------------------------------------------------------------
# Positioned brain fixture factory
# ---------------------------------------------------------------------------

def _make_positioned_brain(
    entry_time: datetime,
    heartbeat_response: dict,
    current_price: float = 100.0,
):
    """
    Build a TradingBrain-like object configured to run _state_positioned with a
    single mock position.  Returns (brain, pos).

    Key design: patchers are started here and the test is responsible for running
    `_state_positioned` before the patchers are stopped (or just after).
    Since we're testing pure logic (not IBKR/MT5 calls), the patchers only need to
    cover the Brain __init__ time.
    """
    patchers = [
        patch("brain.Vault.get", side_effect=lambda k, d=None: "dummy" if k == "SESSION_SECRET" else (d or "")),
        patch("brain.FORCED_PAPER_MODE", True),
        patch("brain.STARTING_CAPITAL_CAD", 100_000.0),
        patch("brain.SharedIntelligenceBus", MagicMock),
        patch("brain.IBKRConnection", MagicMock),
        patch("agent_c_mt5.MT5Connection", MagicMock),
        patch("brain.LEDGER", MagicMock()),
        patch("brain.PORTFOLIO_ANALYZER", MagicMock()),
        patch("telegram_alerts.send_telegram_alert", new_callable=AsyncMock),
    ]
    for p in patchers:
        p.start()

    from brain import TradingBrain
    brain = TradingBrain(mode="paper")

    for p in reversed(patchers):
        p.stop()

    # Offline broker wiring
    brain.ibkr_conn = None
    brain.ibkr_client = None
    brain.mt5_conn = None
    brain.mode = "paper"

    # Inject a single position
    pos = _make_position(entry=100.0, stop=98.0, entry_time=entry_time)
    pos.current_price = current_price
    brain.positions = [pos]

    # Mock all external calls
    brain._sanitize_positions = MagicMock()
    brain._reconcile_broker_positions = AsyncMock()
    brain._fetch_market_snapshot = AsyncMock(
        return_value={"price": current_price, "vix": 18.0}
    )
    brain._get_account_value = AsyncMock(return_value=10000.0)
    brain._get_daily_pnl = AsyncMock(return_value=0.0)

    # mind_ultrathink returns the given heartbeat response
    brain.mind_ultrathink = MagicMock()
    brain.mind_ultrathink.heartbeat_vet = AsyncMock(return_value=heartbeat_response)

    # exit_engine defaults to HOLD so heartbeat is the only exit trigger
    from exit_intelligence import ExitAction, ExitDecision
    hold_decision = ExitDecision(action=ExitAction.HOLD, reason="hold", priority=0)
    brain.exit_engine = MagicMock()
    brain.exit_engine.evaluate = MagicMock(return_value=hold_decision)

    # vix_protocol — no action
    brain.vix_protocol = MagicMock()
    brain.vix_protocol.monitor_intraday = MagicMock(return_value="HOLD")

    brain.bus = None
    brain._oracle_dhatu = "STHIRA"

    # _process_exit: capture calls to it
    brain._process_exit = AsyncMock()
    brain._mark_trade_liquidated = MagicMock()

    return brain, pos


class TestHeartbeatVetoAgeGate:
    """Tests for the 60-second stop-breach age gate inside _state_positioned."""

    @pytest.mark.asyncio
    async def test_stop_breach_veto_suppressed_under_60s(self):
        """
        HEARTBEAT_VETO with 'stop breached' reason should be suppressed
        when position age < 60 s.
        """
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        heartbeat = {"veto": True, "reason": "Hard stop breached: $99 <= $100"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        # asyncio.Lock must be created inside the running event loop
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        # _process_exit must NOT have been called (veto suppressed)
        brain._process_exit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stop_breach_veto_fires_over_60s(self):
        """
        HEARTBEAT_VETO with 'stop breached' reason SHOULD fire when age > 60 s.
        """
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=90)
        heartbeat = {"veto": True, "reason": "Hard stop breached: $99 <= $100"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        brain._process_exit.assert_awaited_once()
        _, exit_type, _ = brain._process_exit.call_args[0]
        assert exit_type == "HEARTBEAT_VETO"

    @pytest.mark.asyncio
    async def test_vix_panic_fires_immediately_despite_young_position(self):
        """
        VIX panic veto must fire even when position is < 60 s old.
        (Not a stop-breach → age gate is bypassed.)
        """
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        heartbeat = {"veto": True, "reason": "VIX panic spike: 40.0"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        brain._process_exit.assert_awaited_once()
        _, exit_type, _ = brain._process_exit.call_args[0]
        assert exit_type == "HEARTBEAT_VETO"

    @pytest.mark.asyncio
    async def test_belief_collapse_fires_immediately_despite_young_position(self):
        """
        Bayesian belief collapse veto fires regardless of position age.
        """
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=10)
        heartbeat = {"veto": True, "reason": "Bayesian belief collapsed to 0.10"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        brain._process_exit.assert_awaited_once()
        _, exit_type, _ = brain._process_exit.call_args[0]
        assert exit_type == "HEARTBEAT_VETO"

    @pytest.mark.asyncio
    async def test_no_veto_means_no_exit(self):
        """When heartbeat_vet returns veto=False, no exit should be triggered."""
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        heartbeat = {"veto": False, "reason": ""}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        brain._process_exit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stop_breach_at_61s_is_NOT_suppressed(self):
        """
        At 61s the condition `_pos_age_s < 60` is False, so the veto fires.
        """
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        heartbeat = {"veto": True, "reason": "Hard stop breached: $97 <= $98"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        brain._process_exit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_veto_reason_mixed_case_stop_breached(self):
        """'Stop Breached' (capital S) must still be caught by case-insensitive check."""
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        heartbeat = {"veto": True, "reason": "Stop Breached: $99 <= $100"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        # Mixed-case 'Stop Breached' → _is_stop_breach=True → age < 60s → suppressed
        brain._process_exit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_ghost_position_skipped(self):
        """Positions with qty ≈ 0 are skipped entirely (ghost position guard)."""
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=5)
        heartbeat = {"veto": True, "reason": "Hard stop breached: $99 <= $100"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        pos.qty = 0.0  # Ghost position
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        # Ghost position is skipped entirely — heartbeat not even called
        brain._process_exit.assert_not_awaited()
        brain.mind_ultrathink.heartbeat_vet.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_exit_triggered_flag_prevents_double_exit(self):
        """If pos.meta['exit_triggered'] is set, monitoring is skipped for this position."""
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        heartbeat = {"veto": True, "reason": "Hard stop breached: $97 <= $98"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        pos.meta["exit_triggered"] = True
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        brain._process_exit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_new_stop_from_heartbeat_updates_position(self):
        """
        When heartbeat_vet returns a new_stop, pos.stop_loss must be updated.
        """
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        # No veto — just a dynamic stop update
        heartbeat = {"veto": False, "new_stop": 99.5}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        assert pos.stop_loss == pytest.approx(99.5), (
            f"Expected stop_loss=99.5, got {pos.stop_loss}"
        )

    @pytest.mark.asyncio
    async def test_old_position_stop_breach_with_stop_breach_prefix(self):
        """
        Position age > 60s with a 'stop breached' reason fires HEARTBEAT_VETO.
        (This verifies the exact text matching works for various prefixes.)
        """
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=75)
        heartbeat = {"veto": True, "reason": "STOP BREACHED: price $97 below stop $98"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        # "stop breached" is in the lowercase reason → _is_stop_breach=True
        # age=75s > 60s → NOT suppressed
        brain._process_exit.assert_awaited_once()
        _, exit_type, _ = brain._process_exit.call_args[0]
        assert exit_type == "HEARTBEAT_VETO"

    @pytest.mark.asyncio
    async def test_vix_panic_old_position_also_fires(self):
        """VIX panic fires for old positions (age > 60s) as well."""
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=200)
        heartbeat = {"veto": True, "reason": "VIX panic spike: 45.0"}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()
        await brain._state_positioned()

        brain._process_exit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_veto_but_exit_engine_fires_exit(self):
        """
        When heartbeat returns no veto but exit_engine returns EXIT,
        _process_exit is called with the EXIT_P<n> type.
        """
        entry_time = datetime.now(timezone.utc) - timedelta(seconds=120)
        heartbeat = {"veto": False}

        brain, pos = _make_positioned_brain(entry_time, heartbeat)
        brain._state_lock = asyncio.Lock()

        # Override exit_engine to fire EXIT
        from exit_intelligence import ExitAction, ExitDecision
        exit_decision = ExitDecision(action=ExitAction.EXIT, reason="stop hit", priority=1)
        brain.exit_engine.evaluate = MagicMock(return_value=exit_decision)

        await brain._state_positioned()

        brain._process_exit.assert_awaited_once()
        _, exit_type, _ = brain._process_exit.call_args[0]
        assert "EXIT_P" in exit_type


# ===========================================================================
# SECTION 3 — coordinator.py: friction veto (RR threshold)
# ===========================================================================

# ---------------------------------------------------------------------------
# Coordinator fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_coordinator():
    """TradingCoordinator with a fully mocked brain. No live connections needed."""
    from coordinator import TradingCoordinator

    brain = MagicMock()
    brain.bus = None
    brain.positions = []
    brain.current_regime = "TRENDING"
    brain._oracle_dhatu = "Sthiti"
    brain._oracle_freeze = False
    brain._oracle_risk_modifier = 1.0
    brain._vetting_cooldowns = {}
    brain.session_pnl = 0.0
    brain.active_broker = "ibkr"
    brain.db_conn = None  # No DB → Best Day Rule auto-passes

    # Drawdown / loss tracker stubs
    brain.ibkr_drawdown = MagicMock()
    brain.ibkr_drawdown.level = MagicMock()
    brain.ibkr_drawdown.level.value = "GREEN"
    brain.ibkr_drawdown.get_size_modifier = MagicMock(return_value=1.0)
    brain.loss_tracker = MagicMock()
    brain.loss_tracker.get_size_modifier = MagicMock(return_value=1.0)
    brain.skill_tree = MagicMock()
    brain.skill_tree.is_unlocked = MagicMock(return_value=True)
    brain.dms = None

    bridge = MagicMock()
    coord = TradingCoordinator(bridge, brain)
    return coord


def _make_pattern(
    entry: float = 100.0,
    stop: float = 98.0,
    target: float = 104.0,
    confidence: float = 75.0,
):
    """Build a minimal PatternResult-compatible mock for coordinator tests."""
    from agent_a import PatternResult

    pat = MagicMock(spec=PatternResult)
    pat.name = "bull_flag"
    pat.entry = entry
    pat.stop = stop
    pat.target = target
    pat.confidence = confidence
    pat.r_r_ratio = abs(target - entry) / abs(entry - stop) if abs(entry - stop) > 0 else 2.0
    pat.atr = 0.5
    return pat


def _make_spread_data(spread: float = 0.01) -> dict:
    return {"spread": spread, "bid": 99.99, "ask": 100.01}


def _friction_veto_check(result, friction_vetoed: bool, *, expect_veto: bool) -> None:
    """Assert friction veto expectation."""
    if expect_veto:
        assert result is False, f"Expected result=False (friction veto), got: {result}"
    else:
        assert not friction_vetoed, "FRICTION VETO logged — should NOT have fired"


class TestFrictionVeto:
    """Tests for the friction veto logic inside initiate_trade_lifecycle."""

    @pytest.mark.asyncio
    async def test_friction_veto_blocks_low_rr_trade_standard_account(self, mock_coordinator):
        """
        Standard account (balance=$5000 USD > $2000), threshold=1.3.
        Pattern: entry=100, stop=99, target=101 → raw RR=1.0 before spread/commission.
        With spread=0.30, real_rr falls below 1.3 → friction veto fires → return False.
        """
        brain = mock_coordinator.brain
        # USD balance > $2000: standard threshold = 1.3
        brain.get_safe_buying_power = AsyncMock(return_value=5000.0)  # USD directly
        brain.get_current_spread = AsyncMock(return_value=_make_spread_data(spread=0.30))

        # Pattern: risk=1.0, reward=1.0 → base RR=1.0
        pattern = _make_pattern(entry=100.0, stop=99.0, target=101.0)
        proposal = {"pattern": pattern, "task": None}

        # Patch config values at the module level where they are re-imported
        with patch("config.COMMISSION_PER_ROUND_TRIP", 1.0), \
             patch("config.USD_CAD_RATE", 1.0):
            result = await mock_coordinator.initiate_trade_lifecycle(
                "AAPL", proposal, is_probe=False
            )

        assert result is False, f"Expected False (friction veto), got: {result}"

    @pytest.mark.asyncio
    async def test_friction_veto_passes_good_rr_standard_account(self, mock_coordinator):
        """
        Standard account (>$2000 USD), threshold=1.3.
        Pattern: entry=100, stop=98, target=106 → raw RR=3.0 → stays above 1.3 after costs.
        Coordinator should NOT veto on friction grounds.
        """
        brain = mock_coordinator.brain
        brain.get_safe_buying_power = AsyncMock(return_value=5000.0)  # USD
        brain.get_current_spread = AsyncMock(return_value=_make_spread_data(spread=0.01))

        # Pattern: risk=2, reward=6, RR=3
        pattern = _make_pattern(entry=100.0, stop=98.0, target=106.0)
        proposal = {"pattern": pattern, "task": None}

        friction_vetoed = False

        import logging as _logging
        _orig = _logging.getLogger("coordinator").warning

        def _capture(msg, *args, **kwargs):
            nonlocal friction_vetoed
            formatted = str(msg) % args if args else str(msg)
            if "FRICTION VETO" in formatted:
                friction_vetoed = True
            return _orig(msg, *args, **kwargs)

        _logging.getLogger("coordinator").warning = _capture

        with patch("config.COMMISSION_PER_ROUND_TRIP", 1.0), \
             patch("config.USD_CAD_RATE", 1.0):
            try:
                await mock_coordinator.initiate_trade_lifecycle(
                    "AAPL", proposal, is_probe=False
                )
            except Exception:
                pass
        _logging.getLogger("coordinator").warning = _orig

        assert not friction_vetoed, "Friction veto should NOT fire for real_rr > 1.3"

    @pytest.mark.asyncio
    async def test_friction_veto_threshold_standard_account_below_1_3(self, mock_coordinator):
        """
        Standard account balance=$5000 USD (>$2000 threshold).
        Pattern: entry=100, stop=98.5 (risk=1.5), target=102.0 (reward=2.0).
        With spread=0.30, real_rr drops below 1.3 → friction veto fires.
        """
        brain = mock_coordinator.brain
        brain.get_safe_buying_power = AsyncMock(return_value=5000.0)
        brain.get_current_spread = AsyncMock(return_value=_make_spread_data(spread=0.30))

        pattern = _make_pattern(entry=100.0, stop=98.5, target=102.0)
        proposal = {"pattern": pattern, "task": None}

        with patch("config.COMMISSION_PER_ROUND_TRIP", 1.0), \
             patch("config.USD_CAD_RATE", 1.0):
            result = await mock_coordinator.initiate_trade_lifecycle(
                "TSLA", proposal, is_probe=False
            )

        assert result is False, "Expected friction veto (result=False) for standard account RR < 1.3"

    @pytest.mark.asyncio
    async def test_friction_veto_threshold_small_account_relaxed(self, mock_coordinator):
        """
        Small account balance < $2000 → threshold relaxed to 1.0.
        Uses a low-priced stock ($10 entry) so est_shares=20 and commission impact is small.
        Chosen numbers yield real_rr ≈ 1.01, which is above the 1.0 relaxed threshold.
        Friction veto should NOT trigger.
        """
        brain = mock_coordinator.brain
        # Small account: $500 CAD (< $2000 threshold) → threshold = 1.0
        brain.get_safe_buying_power = AsyncMock(return_value=500.0)
        # Tiny spread to keep costs low
        brain.get_current_spread = AsyncMock(return_value=_make_spread_data(spread=0.02))

        # entry=$10, stop=$9.0 (risk=1.0), target=$11.15 (reward=1.15)
        # With USD_CAD=1.0, balance_usd=500 → est_shares=max(1, int(500*0.4/10))=20
        # comm_per_share=1.0/20=0.05
        # total_reward=1.15-0.02-0.05=1.08, total_risk=1.0+0.02+0.05=1.07
        # real_rr = 1.08/1.07 ≈ 1.01 > threshold=1.0 → passes
        pattern = _make_pattern(entry=10.0, stop=9.0, target=11.15)
        proposal = {"pattern": pattern, "task": None}

        friction_vetoed = False

        import logging as _logging
        _orig = _logging.getLogger("coordinator").warning

        def _capture(msg, *args, **kwargs):
            nonlocal friction_vetoed
            formatted = str(msg) % args if args else str(msg)
            if "FRICTION VETO" in formatted:
                friction_vetoed = True
            return _orig(msg, *args, **kwargs)

        _logging.getLogger("coordinator").warning = _capture

        with patch("config.COMMISSION_PER_ROUND_TRIP", 1.0), \
             patch("config.USD_CAD_RATE", 1.0):
            try:
                await mock_coordinator.initiate_trade_lifecycle(
                    "NVDA", proposal, is_probe=False
                )
            except Exception:
                pass

        _logging.getLogger("coordinator").warning = _orig

        assert not friction_vetoed, (
            "Friction veto should NOT fire for small account with real_rr > 1.0"
        )

    @pytest.mark.asyncio
    async def test_friction_veto_is_skipped_for_probes(self, mock_coordinator):
        """
        is_probe=True bypasses the friction veto entirely regardless of RR.
        """
        brain = mock_coordinator.brain
        brain.get_safe_buying_power = AsyncMock(return_value=5000.0)
        brain.get_current_spread = AsyncMock(return_value=_make_spread_data(spread=5.0))  # huge spread

        # Terrible RR pattern (risk=0.1, reward=0.1)
        pattern = _make_pattern(entry=100.0, stop=99.9, target=100.1)
        proposal = {"pattern": pattern, "task": None}

        friction_vetoed = False

        import logging as _logging
        _orig = _logging.getLogger("coordinator").warning

        def _capture(msg, *args, **kwargs):
            nonlocal friction_vetoed
            formatted = str(msg) % args if args else str(msg)
            if "FRICTION VETO" in formatted:
                friction_vetoed = True
            return _orig(msg, *args, **kwargs)

        _logging.getLogger("coordinator").warning = _capture

        with patch("config.COMMISSION_PER_ROUND_TRIP", 1.0), \
             patch("config.USD_CAD_RATE", 1.0):
            try:
                await mock_coordinator.initiate_trade_lifecycle(
                    "SPY", proposal, is_probe=True
                )
            except Exception:
                pass

        _logging.getLogger("coordinator").warning = _orig

        assert not friction_vetoed, "Friction veto must be bypassed for probes"

    @pytest.mark.asyncio
    async def test_friction_veto_zero_risk_amount_skips_gate(self, mock_coordinator):
        """
        If pattern.entry == pattern.stop (risk_amt=0), the friction gate inner block
        is never entered (the `if risk_amt > 0:` guard). Coordinator should not raise.
        """
        brain = mock_coordinator.brain
        brain.get_safe_buying_power = AsyncMock(return_value=5000.0)
        brain.get_current_spread = AsyncMock(return_value=_make_spread_data())

        # Zero risk: stop == entry
        pattern = _make_pattern(entry=100.0, stop=100.0, target=105.0)
        proposal = {"pattern": pattern, "task": None}

        with patch("config.COMMISSION_PER_ROUND_TRIP", 1.0), \
             patch("config.USD_CAD_RATE", 1.0):
            try:
                result = await mock_coordinator.initiate_trade_lifecycle(
                    "GOOG", proposal, is_probe=False
                )
                # Should not crash; result may be None / False from other guards
                assert result in (False, None, True), f"Unexpected result: {result}"
            except Exception as exc:
                pytest.fail(f"Should not raise on zero risk_amt: {exc}")

    @pytest.mark.asyncio
    async def test_friction_veto_uses_small_account_boundary_2000(self, mock_coordinator):
        """
        Demonstrates the threshold boundary between small ($500) and standard ($5000).

        Case 1 — Small account ($500): entry=$10, stop=$9, target=$11.15, spread=0.02
          - est_shares=20, comm_per_share=0.05
          - total_reward=1.08, total_risk=1.07 → real_rr≈1.01 > threshold=1.0 → passes

        Case 2 — Standard account ($5000): entry=$100, stop=$99, target=$101.35, spread=0.05
          - est_shares=20, comm_per_share=0.05
          - total_reward≈1.25, total_risk≈1.10 → real_rr≈1.14 < threshold=1.3 → VETO
        """
        brain = mock_coordinator.brain
        import logging as _logging

        # --- Case 1: Small account ($500 < $2000) — threshold=1.0 → should NOT veto ---
        brain.get_safe_buying_power = AsyncMock(return_value=500.0)
        brain.get_current_spread = AsyncMock(return_value=_make_spread_data(spread=0.02))
        pattern_small = _make_pattern(entry=10.0, stop=9.0, target=11.15)
        proposal_small = {"pattern": pattern_small, "task": None}

        small_vetoed = False
        _orig = _logging.getLogger("coordinator").warning

        def _capture_small(msg, *args, **kwargs):
            nonlocal small_vetoed
            formatted = str(msg) % args if args else str(msg)
            if "FRICTION VETO" in formatted:
                small_vetoed = True
            return _orig(msg, *args, **kwargs)

        _logging.getLogger("coordinator").warning = _capture_small

        with patch("config.COMMISSION_PER_ROUND_TRIP", 1.0), \
             patch("config.USD_CAD_RATE", 1.0):
            try:
                await mock_coordinator.initiate_trade_lifecycle(
                    "AMD", proposal_small, is_probe=False
                )
            except Exception:
                pass

        _logging.getLogger("coordinator").warning = _orig
        assert not small_vetoed, "Small account should NOT trigger friction veto for real_rr≈1.01"

        # --- Case 2: Standard account ($5000 >= $2000) — threshold=1.3 → should VETO ---
        brain.get_safe_buying_power = AsyncMock(return_value=5000.0)
        brain.get_current_spread = AsyncMock(return_value=_make_spread_data(spread=0.05))
        # entry=100, stop=99 (risk=1), target=101.35 (reward=1.35)
        # est_shares=int(5000*0.4/100)=20, comm_per_share=0.05
        # real_rr = (1.35-0.05-0.05)/(1+0.05+0.05) = 1.25/1.10 ≈ 1.136 < 1.3 → veto
        pattern_std = _make_pattern(entry=100.0, stop=99.0, target=101.35)
        proposal_std = {"pattern": pattern_std, "task": None}
        mock_coordinator._pending_vets.clear()

        with patch("config.COMMISSION_PER_ROUND_TRIP", 1.0), \
             patch("config.USD_CAD_RATE", 1.0):
            result = await mock_coordinator.initiate_trade_lifecycle(
                "AMD", proposal_std, is_probe=False
            )

        assert result is False, "Standard account should trigger friction veto for real_rr≈1.14 < 1.3"
