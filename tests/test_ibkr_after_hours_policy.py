import sys
from unittest.mock import MagicMock

sys.path.insert(0, "src")

import agent_c_ibkr
from agent_c_ibkr import IBKRConnection


def _ready_ibkr_connection(monkeypatch):
    ib = MagicMock()
    ib.wrapper.accounts = ["TEST123"]
    conn = IBKRConnection(ib_client=ib)
    conn.get_account_value = MagicMock(return_value=250_000.0)
    conn.get_margin_cushion = MagicMock(return_value=0.50)
    conn.is_extended_hours = MagicMock(return_value=True)
    conn.is_near_close = MagicMock(return_value=False)
    monkeypatch.setattr(agent_c_ibkr.TradingStateManager, "allow_order", lambda is_close=False: (True, "OK"))
    monkeypatch.setattr(agent_c_ibkr.ORDER_THROTTLER, "can_submit", lambda: True)
    monkeypatch.setattr(agent_c_ibkr.RiskInvariants, "check_notional", lambda *_args: True)
    return conn


def test_ibkr_after_hours_blocks_new_entries_by_default(monkeypatch):
    monkeypatch.delenv("SOVEREIGN_ALLOW_AFTER_HOURS_IBKR_ENTRIES", raising=False)
    conn = _ready_ibkr_connection(monkeypatch)

    allowed, reason = conn.validate_order_pre_flight(
        "MSFT",
        "BUY",
        10,
        410.0,
        account_id="TEST123",
        is_close=False,
    )

    assert allowed is False
    assert "MARKET_CLOSED" in reason
    assert "SOVEREIGN_ALLOW_AFTER_HOURS_IBKR_ENTRIES=1" in reason


def test_ibkr_after_hours_allows_exits(monkeypatch):
    monkeypatch.delenv("SOVEREIGN_ALLOW_AFTER_HOURS_IBKR_ENTRIES", raising=False)
    conn = _ready_ibkr_connection(monkeypatch)

    allowed, reason = conn.validate_order_pre_flight(
        "MSFT",
        "SELL",
        10,
        410.0,
        account_id="TEST123",
        is_close=True,
    )

    assert allowed is True
    assert reason == "PROCEED"


def test_ibkr_after_hours_allows_explicit_entry_override(monkeypatch):
    monkeypatch.setenv("SOVEREIGN_ALLOW_AFTER_HOURS_IBKR_ENTRIES", "1")
    conn = _ready_ibkr_connection(monkeypatch)

    allowed, reason = conn.validate_order_pre_flight(
        "MSFT",
        "BUY",
        10,
        410.0,
        account_id="TEST123",
        is_close=False,
    )

    assert allowed is True
    assert reason == "PROCEED"
