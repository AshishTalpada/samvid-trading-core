import asyncio
from datetime import datetime
from unittest.mock import MagicMock

import pytest

from agent_c_ibkr import IBKRConnection


def _connection_with_failed_audit() -> IBKRConnection:
    conn = IBKRConnection.__new__(IBKRConnection)
    conn._last_trade_time = datetime.min
    conn._lock = asyncio.Lock()
    conn._verify_exec_token = MagicMock(return_value=True)
    conn._persist_execution = MagicMock(return_value=False)
    conn.is_connected = MagicMock(return_value=True)
    conn.is_near_close = MagicMock(return_value=False)
    conn.ib = MagicMock()
    return conn


@pytest.mark.asyncio
async def test_single_order_fails_closed_when_audit_write_fails() -> None:
    conn = _connection_with_failed_audit()

    order_id = await conn.place_order(
        "SPY",
        "BUY",
        1,
        limit_price=500.0,
        exec_token="valid",
    )

    assert order_id is None
    conn.ib.placeOrder.assert_not_called()


@pytest.mark.asyncio
async def test_bracket_order_fails_closed_when_audit_write_fails() -> None:
    conn = _connection_with_failed_audit()

    order_ids = await conn.place_bracket_order(
        "SPY",
        "BUY",
        1,
        limit_price=500.0,
        stop_loss=495.0,
        take_profit=510.0,
        exec_token="valid",
    )

    assert order_ids == []
    conn.ib.placeOrder.assert_not_called()


def test_persist_execution_reports_audit_failure() -> None:
    conn = IBKRConnection.__new__(IBKRConnection)
    conn._execution_audit = MagicMock()
    conn._execution_audit.append.side_effect = ValueError("corrupt audit")

    assert conn._persist_execution("SPY", "SINGLE", {"dir": "BUY", "shares": 1}) is False
