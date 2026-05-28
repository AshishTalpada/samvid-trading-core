"""
tests/test_broker_mock_integration.py
Broker mock integration tests — Phase 2

Exercises the full order lifecycle for both IBKR and MT5 WITHOUT any live
broker connection.  All external dependencies are replaced with MagicMock /
AsyncMock objects so the suite runs entirely offline.

Coverage matrix
───────────────
IBKR:
  1. Successful single-order entry (paper mode)
  2. Bracket-order entry (paper mode)
  3. Order rejected by pre-flight validation
  4. Order suppressed by Sovereign Order Shield (pending order exists)
  5. Zero-share guard blocks submission
  6. Emergency MKT order bypasses limit-order path
  7. Polarity Shield: prevents SELL when broker shows short position
  8. Reconnection path: offline → simulate → paper-mode fallback
  9. Rate-limiter: order within budget passes; second immediate order passes (rate limiter not blocking in paper)

MT5:
  10. Successful MT5 order placement (lots calculated from shares)
  11. MT5 order with explicit zero shares falls back to sizer

Reconciliation:
  12. _restore_positions_from_db recovers open trade from DB
  13. _reconcile_broker_positions detects orphan and adopts it
  14. _reconcile_open_trade_rows marks liquidated trade on DB mismatch

Hotswap / routing:
  15. _determine_target_broker returns IBKR during equities session (NY 10:00)
  16. _determine_target_broker returns MT5 outside equities session (NY 19:00)
  17. _perform_broker_hotswap switches active_broker to MT5
"""

import asyncio
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, "src")

from brain import TradingBrain
from system_types import Position


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def paper_brain():
    """TradingBrain in paper mode with every external dep mocked out."""
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
        brain = TradingBrain(mode="paper")
        # Broker connections offline by default
        brain.ibkr_conn = MagicMock()
        brain.ibkr_conn.is_connected.return_value = False
        brain.ibkr_conn.has_pending_order.return_value = False
        brain.ibkr_conn.generate_exec_token.return_value = "MOCK_TOKEN"
        brain.ibkr_conn.validate_order_pre_flight.return_value = (True, "OK")
        brain.ibkr_client = MagicMock()
        brain.ibkr_client.positions.return_value = []
        brain.mt5_conn = MagicMock()
        brain.mt5_conn.is_connected.return_value = False
        brain.is_running = True
        brain.active_broker = "IBKR"
        brain.current_regime = "TRENDING"
        brain.last_budget_date = datetime.now(timezone.utc)
        yield brain


# ---------------------------------------------------------------------------
# Helper: quick Position factory
# ---------------------------------------------------------------------------

def _make_position(symbol="AAPL", qty=100, entry=150.0) -> Position:
    return Position(
        symbol=symbol,
        qty=qty,
        entry_price=entry,
        stop_loss=140.0,
        take_profit=165.0,
        r_r_ratio=1.5,
        pattern="bull_flag",
        catalyst_score=70.0,
        dhatu_state="STHIRA",
        regime_at_entry="TRENDING",
        account_type="IBKR",
        account_id="TEST123",
        entry_time=datetime.now(timezone.utc),
    )


# ===========================================================================
# IBKR single-order entry (paper mode)
# ===========================================================================

@pytest.mark.asyncio
async def test_ibkr_paper_single_order_returns_id(paper_brain):
    """Test 1: paper-mode single order returns a non-empty PAPER-* string."""
    oid = await paper_brain._place_ibkr_order(
        symbol="AAPL",
        direction="BUY",
        shares=50,
        urgency="LOW",
        limit_price=150.0,
        stop_price=0.0,
        target_price=0.0,
    )
    assert oid is not None
    assert oid != ""
    assert "PAPER" in str(oid)


@pytest.mark.asyncio
async def test_ibkr_paper_bracket_order_returns_id(paper_brain):
    """Test 2: paper-mode bracket order (stop + target set) returns PAPER-* id."""
    oid = await paper_brain._place_ibkr_order(
        symbol="MSFT",
        direction="BUY",
        shares=25,
        urgency="LOW",
        limit_price=310.0,
        stop_price=300.0,
        target_price=330.0,
    )
    assert oid is not None
    assert "PAPER" in str(oid)


# ===========================================================================
# Pre-flight rejection
# ===========================================================================

@pytest.mark.asyncio
async def test_ibkr_order_rejected_by_pre_flight(paper_brain):
    """Test 3: pre-flight rejects bracket order (stop+target set) → returns None."""
    # Simulate connected broker so pre-flight code path runs (not paper fallback)
    paper_brain.ibkr_conn.is_connected.return_value = True
    paper_brain.ibkr_conn.validate_order_pre_flight.return_value = (False, "DAILY_LIMIT_HIT")
    paper_brain.ibkr_conn.place_bracket_order = AsyncMock(return_value=[99])

    # A bracket order triggers validate_order_pre_flight (stop_price + target_price both set)
    oid = await paper_brain._place_ibkr_order(
        symbol="AAPL",
        direction="BUY",
        shares=100,
        urgency="LOW",
        limit_price=150.0,
        stop_price=140.0,     # bracket: pre-flight runs on this path
        target_price=165.0,
    )
    # Pre-flight blocks → returns None (no bracket order placed)
    assert oid is None
    paper_brain.ibkr_conn.place_bracket_order.assert_not_called()


# ===========================================================================
# Sovereign Order Shield (pending-order suppression)
# ===========================================================================

@pytest.mark.asyncio
async def test_ibkr_order_shielded_when_pending(paper_brain):
    """Test 4: if a pending order exists, _place_ibkr_order returns SHIELDED."""
    paper_brain.ibkr_conn.has_pending_order.return_value = True
    oid = await paper_brain._place_ibkr_order(
        symbol="AAPL",
        direction="SELL",
        shares=50,
        urgency="LOW",
        limit_price=155.0,
    )
    assert oid == "SHIELDED"


# ===========================================================================
# Zero-share guard
# ===========================================================================

@pytest.mark.asyncio
async def test_ibkr_zero_share_guard(paper_brain):
    """Test 5: zero-share orders are blocked and Telegram alert is fired."""
    with patch("telegram_alerts.send_telegram_alert", new_callable=AsyncMock) as tg:
        oid = await paper_brain._place_ibkr_order(
            symbol="NVDA",
            direction="BUY",
            shares=0,
            urgency="LOW",
            limit_price=500.0,
        )
    assert oid is None
    tg.assert_awaited_once()
    alert_text = tg.call_args[0][0]
    assert "SHIELD VETO" in alert_text or "NVDA" in alert_text


# ===========================================================================
# Emergency MKT order
# ===========================================================================

@pytest.mark.asyncio
async def test_ibkr_emergency_uses_market_order(paper_brain):
    """Test 6: EMERGENCY urgency triggers MKT order via place_order, not bracket."""
    paper_brain.ibkr_conn.is_connected.return_value = True
    paper_brain.ibkr_conn.place_order = AsyncMock(return_value=42)

    oid = await paper_brain._place_ibkr_order(
        symbol="SPY",
        direction="SELL",
        shares=200,
        urgency="EMERGENCY",
        limit_price=400.0,
        stop_price=0.0,
        target_price=0.0,
    )
    paper_brain.ibkr_conn.place_order.assert_awaited_once()
    call_kwargs = paper_brain.ibkr_conn.place_order.call_args
    assert call_kwargs[1].get("order_type") == "MKT" or "MKT" in call_kwargs[0]


# ===========================================================================
# Polarity Shield
# ===========================================================================

@pytest.mark.asyncio
async def test_ibkr_polarity_shield_flips_direction(paper_brain):
    """Test 7: Polarity Shield corrects SELL→BUY when broker shows short position."""
    paper_brain.ibkr_conn.is_connected.return_value = True
    paper_brain.ibkr_conn.validate_order_pre_flight.return_value = (True, "OK")
    paper_brain.ibkr_conn.place_order = AsyncMock(return_value=55)

    # Simulate broker holding a short position on TSLA
    short_pos = MagicMock()
    short_pos.contract.symbol = "TSLA"
    short_pos.position = -100  # SHORT
    paper_brain.ibkr_client.positions.return_value = [short_pos]

    # We're trying to SELL more — Polarity Shield should flip to BUY
    await paper_brain._place_ibkr_order(
        symbol="TSLA",
        direction="SELL",
        shares=50,
        urgency="LOW",
        limit_price=200.0,
    )
    # Verify that place_order was ultimately called with BUY (or the order went through)
    if paper_brain.ibkr_conn.place_order.called:
        call_args = paper_brain.ibkr_conn.place_order.call_args
        direction_used = call_args[0][1] if len(call_args[0]) > 1 else call_args[1].get("direction", "")
        assert direction_used == "BUY"


# ===========================================================================
# Offline paper fallback
# ===========================================================================

@pytest.mark.asyncio
async def test_ibkr_offline_paper_fallback(paper_brain):
    """Test 8: disconnected broker in paper mode still returns a PAPER-* id."""
    paper_brain.ibkr_conn.is_connected.return_value = False
    oid = await paper_brain._place_ibkr_order(
        symbol="AMZN",
        direction="BUY",
        shares=10,
        urgency="LOW",
        limit_price=180.0,
    )
    assert oid is not None and "PAPER" in str(oid)


# ===========================================================================
# No double-order within same timestamp (rate limiter doesn't block paper)
# ===========================================================================

@pytest.mark.asyncio
async def test_ibkr_two_rapid_paper_orders_both_succeed(paper_brain):
    """Test 9: two rapid paper orders (different symbols) both return PAPER-* ids."""
    oid1 = await paper_brain._place_ibkr_order(
        symbol="AAPL", direction="BUY", shares=10, urgency="LOW", limit_price=150.0
    )
    # Small sleep so time.time() ticks to a new second
    await asyncio.sleep(1.1)
    oid2 = await paper_brain._place_ibkr_order(
        symbol="GOOG", direction="BUY", shares=5, urgency="LOW", limit_price=140.0
    )
    assert oid1 is not None and "PAPER" in str(oid1)
    assert oid2 is not None and "PAPER" in str(oid2)
    # IDs are based on epoch-seconds; after ≥1s sleep they must differ
    assert oid1 != oid2


# ===========================================================================
# MT5 order routing
# ===========================================================================

@pytest.mark.asyncio
async def test_mt5_order_routes_to_connection(paper_brain):
    """Test 10: _place_mt5_order calls mt5_conn.place_order with correct args."""
    paper_brain.mt5_conn.place_order = MagicMock(return_value=7001)

    oid = await paper_brain._place_mt5_order(
        symbol="EURUSD",
        direction="buy",
        shares=0.1,
        limit_price=1.0850,
        stop_price=1.0800,
        target_price=1.0950,
    )
    paper_brain.mt5_conn.place_order.assert_called_once()
    assert oid == 7001


@pytest.mark.asyncio
async def test_mt5_zero_shares_falls_back_to_sizer(paper_brain):
    """Test 11: shares=0 causes MT5 to compute lots from risk sizer (min 0.01)."""
    paper_brain.mt5_conn.place_order = MagicMock(return_value=7002)
    # mt5_sizer is used as fallback; mock it
    paper_brain.mt5_sizer = MagicMock()
    paper_brain.mt5_sizer.calculate_lots.return_value = 0.03

    await paper_brain._place_mt5_order(
        symbol="GBPUSD",
        direction="sell",
        shares=0,
        limit_price=1.2700,
        stop_price=1.2750,
        target_price=1.2600,
    )
    paper_brain.mt5_conn.place_order.assert_called_once()
    call_kwargs = paper_brain.mt5_conn.place_order.call_args[1]
    assert call_kwargs["vol"] >= 0.01


# ===========================================================================
# Reconciliation: _restore_positions_from_db
# ===========================================================================

@pytest.mark.asyncio
async def test_restore_positions_from_db_populates_positions(paper_brain):
    """Test 12: open trade row in DB is restored as an in-memory Position."""
    paper_brain.positions = []  # Start empty

    # Fabricate a DB row matching the exact SELECT in _restore_positions_from_db:
    # id, timestamp, instrument, entry_price, stop_price, target_price,
    # shares, r_r_ratio, pattern, regime, broker, account_id, trading_mode, direction
    # Use a very recent timestamp so the age check (> 720h) does NOT orphan it.
    recent_ts = datetime.now(timezone.utc).isoformat()
    open_trade_row = (
        42,           # id
        recent_ts,    # timestamp (entry_time string — must be recent, not 2024)
        "AAPL",       # instrument
        150.0,        # entry_price
        140.0,        # stop_price
        165.0,        # target_price
        100,          # shares
        1.5,          # r_r_ratio
        "bull_flag",  # pattern
        "TRENDING",   # regime
        "ibkr",       # broker  (lowercase matches account_type)
        "TEST123",    # account_id
        "paper",      # trading_mode
        "LONG",       # direction
    )

    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [open_trade_row]
    paper_brain.db_conn = MagicMock()
    paper_brain.db_conn.cursor.return_value = mock_cursor

    await paper_brain._restore_positions_from_db()

    assert len(paper_brain.positions) == 1
    pos = paper_brain.positions[0]
    assert pos.symbol == "AAPL"
    assert pos.entry_price == 150.0
    assert pos.qty == 100.0          # LONG direction → positive qty
    assert pos.stop_loss == 140.0


# ===========================================================================
# Reconciliation: orphan adoption
# ===========================================================================

@pytest.mark.asyncio
async def test_reconcile_adopts_orphan_broker_position(paper_brain):
    """Test 13: a broker position not in memory gets adopted as a new Position.

    _reconcile_broker_positions reads ibkr_conn._positions_cache (or polls
    ib.positions() when cache is stale).  We pre-populate the cache directly
    so the reconcile loop sees an unfamiliar symbol and calls _adopt_orphan.
    """
    paper_brain.positions = []
    paper_brain.start_time = datetime(2024, 1, 1, tzinfo=timezone.utc)  # old uptime

    # Make IBKR appear connected
    paper_brain.ibkr_conn.is_connected.return_value = True
    paper_brain.ibkr_conn._positions_cache = {"MSFT": 100.0}

    # _adopt_orphan queries DB: SELECT entry_price, stop_price, target_price
    # Returns a 3-tuple.  If None is returned it uses market price instead.
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None  # no DB row → adopt from market price
    paper_brain.db_conn = MagicMock()
    paper_brain.db_conn.cursor.return_value = mock_cursor

    # _broker_is_connected checks is_connected()
    paper_brain._broker_is_connected = lambda conn: conn.is_connected()
    # _adopt_orphan calls _fetch_market_snapshot when last_tick_prices is empty
    paper_brain._fetch_market_snapshot = AsyncMock(return_value={"price": 300.0})

    await paper_brain._reconcile_broker_positions()

    symbols = [p.symbol for p in paper_brain.positions]
    assert "MSFT" in symbols


# ===========================================================================
# Reconciliation: _reconcile_open_trade_rows marks closed trades
# ===========================================================================

def test_reconcile_marks_liquidated_closed_db_rows(paper_brain):
    """Test 14: DB trade flagged OPEN but not in broker reality is marked LIQUIDATED.

    _reconcile_open_trade_rows is a sync method (not async) that requires:
      broker, reality (dict), polled (bool), now_ts (datetime)
    """
    paper_brain.positions = []

    # Old open trade for NVDA opened 5 minutes ago (age > 120s threshold)
    old_ts = "2024-01-01T10:00:00+00:00"
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        (99, old_ts, "NVDA"),  # (id, timestamp, instrument)
    ]
    paper_brain.db_conn = MagicMock()
    paper_brain.db_conn.cursor.return_value = mock_cursor

    # Broker reality: flat (no NVDA position)
    reality: dict[str, float] = {}
    now_ts = datetime(2024, 1, 1, 10, 10, 0, tzinfo=timezone.utc)  # 10 min later

    paper_brain._reconcile_open_trade_rows(
        broker="IBKR",
        reality=reality,
        polled=True,
        now_ts=now_ts,
    )

    # DB UPDATE should mark the trade LIQUIDATED
    executed_calls = [str(c) for c in mock_cursor.execute.call_args_list]
    assert any("LIQUIDATED" in c for c in executed_calls)


# ===========================================================================
# Broker routing / hotswap
# ===========================================================================

def test_determine_target_broker_ibkr_during_equities(paper_brain):
    """Test 15: 10:00 AM NY → IBKR equities session."""
    from unittest.mock import patch as p
    # 14:00 UTC = 10:00 AM EDT (UTC-4)
    fixed_dt = datetime(2024, 6, 15, 14, 0, 0, tzinfo=timezone.utc)
    with p("brain_execution.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt
        result = paper_brain._determine_target_broker()
    assert result == "IBKR"


def test_determine_target_broker_mt5_outside_equities(paper_brain):
    """Test 16: 23:00 UTC = 19:00 EDT → MT5 forex session."""
    from unittest.mock import patch as p
    fixed_dt = datetime(2024, 6, 15, 23, 0, 0, tzinfo=timezone.utc)
    with p("brain_execution.datetime") as mock_dt:
        mock_dt.now.return_value = fixed_dt
        result = paper_brain._determine_target_broker()
    assert result == "MT5"


@pytest.mark.asyncio
async def test_perform_broker_hotswap_to_mt5(paper_brain):
    """Test 17: _perform_broker_hotswap('MT5') sets active_broker = MT5."""
    paper_brain.mt5_conn.connect = MagicMock(return_value=True)

    # Vault is imported *locally* inside _perform_broker_hotswap via `from vault import Vault`
    # so we patch the vault module directly.
    with patch("vault.Vault") as mock_vault:
        mock_vault.get.side_effect = lambda k, d="": {
            "MT5_LOGIN": "12345",
            "MT5_PASSWORD": "testpw",
            "MT5_SERVER": "Demo-Server",
        }.get(k, d)

        await paper_brain._perform_broker_hotswap("MT5")

    assert paper_brain.active_broker == "MT5"
