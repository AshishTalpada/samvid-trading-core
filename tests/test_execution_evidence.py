import json

import pytest

from execution_audit import ExecutionAuditLog
from execution_evidence import build_execution_evidence


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
