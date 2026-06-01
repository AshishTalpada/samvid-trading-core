import asyncio
import json
import sqlite3
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent_c_ibkr import IBKRConnection
from brain import TradingBrain


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


def test_cancelled_exit_releases_position_latch_and_updates_active_strikes() -> None:
    conn = IBKRConnection.__new__(IBKRConnection)
    conn._execution_audit = MagicMock()
    conn._intent_id_by_order_id = {}
    position = SimpleNamespace(symbol="SPY", qty=2, meta={"exit_triggered": True})
    conn.brain = SimpleNamespace(
        positions=[position],
        _exit_last_attempt={"SPY": datetime.now()},
        _exit_failure_count={},
    )
    trade = SimpleNamespace(
        contract=SimpleNamespace(symbol="SPY"),
        order=SimpleNamespace(
            orderId=123,
            parentId=0,
            action="SELL",
            orderType="MKT",
            totalQuantity=2,
        ),
        orderStatus=SimpleNamespace(status="Cancelled", filled=0, remaining=2),
        log=[],
    )

    with patch("threading.Thread"):
        conn._on_order_status(trade)

    assert "exit_triggered" not in position.meta
    assert "SPY" not in conn.brain._exit_last_attempt
    assert conn.brain._exit_failure_count["SPY"] == 1


def test_persistent_order_schema_upgrades_legacy_cache() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE persistent_orders ("
        "orderId INTEGER PRIMARY KEY, symbol TEXT, status TEXT, "
        "filled REAL, remaining REAL, last_update TEXT)"
    )

    IBKRConnection._ensure_persistent_orders_schema(conn)

    columns = {row[1] for row in conn.execute("PRAGMA table_info(persistent_orders)")}
    assert {"parent_id", "intent_id"} <= columns


def test_terminal_status_snapshot_retains_lineage(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    conn = IBKRConnection.__new__(IBKRConnection)
    conn._intent_id_by_order_id = {"123": "intent-123"}
    trade = SimpleNamespace(
        order=SimpleNamespace(orderId=123, parentId=0),
        orderStatus=SimpleNamespace(status="Filled", filled=2, remaining=0),
    )

    conn._persist_order_status_snapshot(trade, "SPY", "Filled")

    db = sqlite3.connect(tmp_path / "data" / "trading.db")
    row = db.execute(
        "SELECT status, filled, remaining, intent_id FROM persistent_orders WHERE orderId = 123"
    ).fetchone()
    assert row == ("Filled", 2.0, 0.0, "intent-123")


@pytest.mark.asyncio
async def test_recovery_restores_durable_intent_lineage(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db = sqlite3.connect(data_dir / "trading.db")
    IBKRConnection._ensure_persistent_orders_schema(db)
    db.execute(
        "INSERT INTO persistent_orders "
        "(orderId, symbol, status, filled, remaining, last_update, parent_id, intent_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (123, "SPY", "Submitted", 0, 2, "now", 0, "intent-123"),
    )
    db.commit()
    db.close()

    conn = IBKRConnection.__new__(IBKRConnection)
    conn.is_connected = MagicMock(return_value=True)
    conn.ib = SimpleNamespace(
        reqAllOpenOrdersAsync=AsyncMock(
            return_value=[SimpleNamespace(order=SimpleNamespace(orderId=123))]
        )
    )
    conn._intent_id_by_order_id = {}
    conn._recovered_orders = set()

    await conn.recover_orphaned_orders()

    assert conn._intent_id_by_order_id == {"123": "intent-123"}
    assert conn._recovered_orders == {123}


@pytest.mark.asyncio
async def test_recovery_classifies_orders_missing_from_broker(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    db = sqlite3.connect(data_dir / "trading.db")
    IBKRConnection._ensure_persistent_orders_schema(db)
    db.execute(
        "INSERT INTO persistent_orders "
        "(orderId, symbol, status, filled, remaining, last_update, parent_id, intent_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (124, "QQQ", "PreSubmitted", 0, 2, "now", 0, None),
    )
    db.commit()
    db.close()

    conn = IBKRConnection.__new__(IBKRConnection)
    conn.is_connected = MagicMock(return_value=True)
    conn.ib = SimpleNamespace(reqAllOpenOrdersAsync=AsyncMock(return_value=[]))
    conn._intent_id_by_order_id = {}
    conn._recovered_orders = set()

    await conn.recover_orphaned_orders()

    db = sqlite3.connect(data_dir / "trading.db")
    status = db.execute(
        "SELECT status FROM persistent_orders WHERE orderId = 124"
    ).fetchone()[0]
    assert status == "ReconciliationRequired"
    assert conn._recovered_orders == {124}


@pytest.mark.asyncio
async def test_ensure_connection_registers_callbacks_and_launches_recovery() -> None:
    conn = IBKRConnection.__new__(IBKRConnection)
    conn.is_connected = MagicMock(return_value=True)
    conn.is_reconnecting = False
    conn._callbacks_registered = False
    conn._setup_callbacks = MagicMock(
        side_effect=lambda: setattr(conn, "_callbacks_registered", True)
    )
    conn._recovered_orders = set()
    conn._background_tasks = set()
    conn.recover_orphaned_orders = AsyncMock()

    result = await conn.ensure_connection()
    await asyncio.sleep(0)

    assert result is True
    conn._setup_callbacks.assert_called_once()
    conn.recover_orphaned_orders.assert_awaited_once()


@pytest.mark.asyncio
async def test_brain_startup_initializes_connected_ibkr_runtime() -> None:
    brain = TradingBrain.__new__(TradingBrain)
    brain.ibkr_conn = SimpleNamespace(ensure_connection=AsyncMock())
    brain._broker_is_connected = MagicMock(return_value=True)

    await brain._initialize_ibkr_runtime()

    brain.ibkr_conn.ensure_connection.assert_awaited_once()


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
