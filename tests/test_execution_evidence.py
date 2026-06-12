import json
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from execution_audit import ExecutionAuditLog
from execution_evidence import build_execution_evidence, repair_trade_ledger_from_execution_audit


def test_execution_evidence_reports_lineage_cost_latency_and_slippage(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    intent = audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=2,
        order_type="SINGLE",
        intent_id="intent-123",
        details={"px": 500.0},
    )
    fill = audit.append(
        event="ORDER_FILL",
        symbol="SPY",
        side="BOT",
        quantity=2,
        order_type="FILL",
        intent_id="intent-123",
        details={"fill_price": 500.25, "lineage_status": "MATCHED"},
    )
    audit.append(
        event="ORDER_COMMISSION",
        symbol="SPY",
        side="BOT",
        quantity=2,
        order_type="COMMISSION",
        intent_id="intent-123",
        details={"commission": 1.25, "lineage_status": "MATCHED"},
    )

    report = build_execution_evidence(path)

    assert report["audit"]["valid"] is True
    assert report["lineage"]["intents"] == 1
    assert report["lineage"]["filled_intents"] == 1
    assert report["lineage"]["intent_fill_rate"] == 1.0
    assert report["lineage"]["matched_fills"] == 1
    assert report["lineage"]["fill_fragments"] == 0
    assert report["costs"]["total_commission"] == 1.25
    assert report["costs"]["total_observed_slippage"] == 0.5
    assert report["latency_ms"]["samples"] == 1
    assert report["latency_ms"]["max"] == pytest.approx(
        (fill["timestamp_ns"] - intent["timestamp_ns"]) / 1_000_000
    )


def test_execution_evidence_counts_unmatched_terminal_events(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    audit.append(
        event="ORDER_STATUS",
        symbol="QQQ",
        side="SELL",
        quantity=3,
        order_type="LMT",
        details={"status": "Cancelled", "lineage_status": "UNMATCHED"},
    )

    report = build_execution_evidence(path)

    assert report["lineage"]["unmatched_lineage_events"] == 1
    assert report["routing"]["terminal_statuses"] == {"Cancelled": 1}


def test_execution_evidence_refuses_tampered_chain(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=1,
        order_type="SINGLE",
    )
    record = json.loads(path.read_text())
    record["quantity"] = 999
    path.write_text(json.dumps(record) + "\n")

    with pytest.raises(ValueError, match="verification failed"):
        build_execution_evidence(path)


def test_execution_evidence_filters_by_timestamp(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    first = audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=1,
        order_type="SINGLE",
    )
    audit.append(
        event="ORDER_INTENT",
        symbol="QQQ",
        side="BUY",
        quantity=1,
        order_type="SINGLE",
    )

    report = build_execution_evidence(path, since_timestamp_ns=first["timestamp_ns"] + 1)

    assert report["audit"]["records_checked"] == 2
    assert report["audit"]["window_records"] == 1
    assert report["lineage"]["intents"] == 1


def test_execution_evidence_classifies_legacy_records_without_intent_id(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    record = audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=1,
        order_type="SINGLE",
    )
    payload = json.loads(path.read_text())
    payload.pop("intent_id")
    payload.pop("hash")
    payload["hash"] = audit._hash_record(payload)
    path.write_text(json.dumps(payload) + "\n")

    report = build_execution_evidence(path)

    assert record["intent_id"]
    assert report["lineage"]["intents"] == 0
    assert report["lineage"]["legacy_records_without_intent_id"] == 1


def test_execution_evidence_reports_fill_fragments_and_overfills(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    audit.append(
        event="ORDER_INTENT",
        symbol="JPM",
        side="SELL",
        quantity=100,
        order_type="SINGLE",
        intent_id="intent-jpm",
        details={"px": 300.0},
    )
    audit.append(
        event="ORDER_FILL",
        symbol="JPM",
        side="SLD",
        quantity=60,
        order_type="FILL",
        intent_id="intent-jpm",
        details={"fill_price": 299.9, "lineage_status": "MATCHED"},
    )
    audit.append(
        event="ORDER_FILL",
        symbol="JPM",
        side="SLD",
        quantity=45,
        order_type="FILL",
        intent_id="intent-jpm",
        details={"fill_price": 299.8, "lineage_status": "MATCHED"},
    )

    report = build_execution_evidence(path)

    assert report["lineage"]["filled_intents"] == 1
    assert report["lineage"]["matched_fills"] == 2
    assert report["lineage"]["fill_fragments"] == 1
    assert report["lineage"]["overfilled_intents"] == 1
    assert report["lineage"]["underfilled_intents"] == 0


def test_execution_audit_repairs_complete_reconciliation_row(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    intent = audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=10,
        order_type="BRACKET",
        intent_id="intent-repair",
        details={"px": 100.0},
    )
    audit.append(
        event="ORDER_FILL",
        symbol="SPY",
        side="BOT",
        quantity=10,
        order_type="FILL",
        intent_id="intent-repair",
        details={"fill_price": 99.5, "lineage_status": "MATCHED"},
    )
    audit.append(
        event="ORDER_COMMISSION",
        symbol="SPY",
        side="BOT",
        quantity=10,
        order_type="COMMISSION",
        intent_id="intent-repair",
        details={"commission": 1.0, "lineage_status": "MATCHED"},
    )
    audit.append(
        event="ORDER_FILL",
        symbol="SPY",
        side="SLD",
        quantity=10,
        order_type="FILL",
        intent_id="intent-repair",
        details={"fill_price": 101.0, "lineage_status": "MATCHED"},
    )
    audit.append(
        event="ORDER_COMMISSION",
        symbol="SPY",
        side="SLD",
        quantity=10,
        order_type="COMMISSION",
        intent_id="intent-repair",
        details={"commission": 1.5, "lineage_status": "MATCHED"},
    )
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE trades (id INTEGER PRIMARY KEY, timestamp TEXT, instrument TEXT, "
        "direction TEXT, entry_price REAL, stop_price REAL, exit_price REAL, shares REAL, "
        "outcome TEXT, pnl_dollars REAL, net_pnl REAL, r_multiple REAL, hold_hours REAL, "
        "commission REAL, slippage REAL, notes TEXT)"
    )
    trade_time = datetime.fromtimestamp(intent["timestamp_ns"] / 1e9, timezone.utc) + timedelta(
        seconds=1
    )
    conn.execute(
        "INSERT INTO trades (timestamp, instrument, direction, entry_price, stop_price, "
        "shares, outcome) VALUES (?, 'SPY', 'LONG', 100.0, 98.0, 0, "
        "'RECONCILIATION_REQUIRED')",
        (trade_time.isoformat(),),
    )

    repairs = repair_trade_ledger_from_execution_audit(conn, path)

    assert len(repairs) == 1
    row = conn.execute(
        "SELECT entry_price, exit_price, shares, outcome, pnl_dollars, net_pnl, "
        "commission, slippage FROM trades"
    ).fetchone()
    assert row[0:3] == pytest.approx((99.5, 101.0, 10.0))
    assert row[3] == "WIN"
    assert row[4:] == pytest.approx((15.0, 12.5, 1.0, 0.0))
    assert repair_trade_ledger_from_execution_audit(conn, path) == []
    conn.close()


def test_execution_audit_does_not_repair_incomplete_exit(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    intent = audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=10,
        order_type="BRACKET",
        intent_id="intent-incomplete",
        details={"px": 100.0},
    )
    audit.append(
        event="ORDER_FILL",
        symbol="SPY",
        side="BOT",
        quantity=10,
        order_type="FILL",
        intent_id="intent-incomplete",
        details={"fill_price": 100.0, "lineage_status": "MATCHED"},
    )
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE trades (id INTEGER PRIMARY KEY, timestamp TEXT, instrument TEXT, "
        "direction TEXT, entry_price REAL, stop_price REAL, outcome TEXT, notes TEXT)"
    )
    trade_time = datetime.fromtimestamp(intent["timestamp_ns"] / 1e9, timezone.utc)
    conn.execute(
        "INSERT INTO trades (timestamp, instrument, direction, entry_price, stop_price, outcome) "
        "VALUES (?, 'SPY', 'LONG', 100.0, 98.0, 'RECONCILIATION_REQUIRED')",
        (trade_time.isoformat(),),
    )

    repairs = repair_trade_ledger_from_execution_audit(conn, path)

    assert repairs == []
    assert conn.execute("SELECT outcome FROM trades").fetchone()[0] == "RECONCILIATION_REQUIRED"
    conn.close()
