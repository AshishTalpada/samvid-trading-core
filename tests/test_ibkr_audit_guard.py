import asyncio
import json
from datetime import datetime
from types import SimpleNamespace
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


def test_persist_execution_mirrors_intent_id_into_recovery_log(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    conn = IBKRConnection.__new__(IBKRConnection)
    conn._execution_audit = MagicMock()
    conn._execution_audit.append.return_value = {
        "hash": "audit-hash",
        "intent_id": "intent-123",
    }

    result = conn._persist_execution("SPY", "SINGLE", {"dir": "BUY", "shares": 1})

    recovery = json.loads((tmp_path / "data" / "execution_persistence.jsonl").read_text())
    assert result is True
    assert recovery["intent_id"] == "intent-123"
    assert recovery["audit_hash"] == "audit-hash"


def test_fill_callback_records_matched_intent_lineage() -> None:
    conn = IBKRConnection.__new__(IBKRConnection)
    conn._execution_audit = MagicMock()
    conn._intent_id_by_order_id = {"123": "intent-123"}
    conn.brain = SimpleNamespace(positions=[])
    trade = SimpleNamespace(
        contract=SimpleNamespace(symbol="SPY"),
        order=SimpleNamespace(orderId=123, parentId=0),
    )
    fill = SimpleNamespace(
        execution=SimpleNamespace(side="BOT", shares=1, avgPrice=500.25),
    )

    conn._on_exec_details(trade, fill)

    conn._execution_audit.append.assert_called_once()
    kwargs = conn._execution_audit.append.call_args.kwargs
    assert kwargs["event"] == "ORDER_FILL"
    assert kwargs["intent_id"] == "intent-123"
    assert kwargs["details"]["lineage_status"] == "MATCHED"


def test_commission_callback_records_matched_intent_lineage() -> None:
    conn = IBKRConnection.__new__(IBKRConnection)
    conn._execution_audit = MagicMock()
    conn._intent_id_by_order_id = {"123": "intent-123"}
    conn.brain = SimpleNamespace(positions=[])
    trade = SimpleNamespace(
        contract=SimpleNamespace(symbol="SPY"),
        order=SimpleNamespace(orderId=123, parentId=0),
    )
    fill = SimpleNamespace(execution=SimpleNamespace(side="BOT", shares=2))
    report = SimpleNamespace(commission=1.25, currency="USD")

    conn._on_commission_report(trade, fill, report)

    kwargs = conn._execution_audit.append.call_args.kwargs
    assert kwargs["event"] == "ORDER_COMMISSION"
    assert kwargs["intent_id"] == "intent-123"
    assert kwargs["details"]["commission"] == 1.25


def test_cancelled_status_records_terminal_lineage() -> None:
    conn = IBKRConnection.__new__(IBKRConnection)
    conn._execution_audit = MagicMock()
    conn._intent_id_by_order_id = {"123": "intent-123"}
    trade = SimpleNamespace(
        contract=SimpleNamespace(symbol="SPY"),
        order=SimpleNamespace(
            orderId=123,
            parentId=0,
            action="BUY",
            orderType="LMT",
            totalQuantity=2,
        ),
        orderStatus=SimpleNamespace(status="Cancelled", filled=0, remaining=2),
    )

    conn._on_order_status(trade)

    kwargs = conn._execution_audit.append.call_args.kwargs
    assert kwargs["event"] == "ORDER_STATUS"
    assert kwargs["intent_id"] == "intent-123"
    assert kwargs["details"]["status"] == "Cancelled"


@pytest.mark.asyncio
async def test_cancel_request_records_operator_action_lineage() -> None:
    conn = IBKRConnection.__new__(IBKRConnection)
    conn._execution_audit = MagicMock()
    conn._intent_id_by_order_id = {"123": "intent-123"}
    conn.is_connected = MagicMock(return_value=True)
    order = SimpleNamespace(
        orderId=123,
        parentId=0,
        action="BUY",
        orderType="LMT",
        totalQuantity=2,
    )
    conn.ib = MagicMock()
    conn.ib.openOrders.return_value = [order]

    result = await conn.cancel_order(123)

    assert result is True
    kwargs = conn._execution_audit.append.call_args.kwargs
    assert kwargs["event"] == "ORDER_CANCEL_REQUEST"
    assert kwargs["intent_id"] == "intent-123"
