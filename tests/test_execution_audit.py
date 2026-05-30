import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from execution_audit import ExecutionAuditLog


def test_execution_audit_is_hash_chained(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)

    first = audit.append(
        event="ORDER_INTENT",
        symbol="spy",
        side="buy",
        quantity=1,
        order_type="LMT",
        details={"price": 500.0},
    )
    second = audit.append(
        event="ORDER_INTENT",
        symbol="qqq",
        side="sell",
        quantity=2,
        order_type="MKT",
        details={"urgency": "HIGH"},
    )

    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert records[0]["previous_hash"] == "GENESIS"
    assert records[1]["previous_hash"] == first["hash"]
    assert records[1]["hash"] == second["hash"]
    assert records[0]["symbol"] == "SPY"
    assert records[1]["side"] == "SELL"
    assert len(records[0]["intent_id"]) == 32
    assert records[0]["intent_id"] != records[1]["intent_id"]
    assert audit.verify() == {
        "valid": True,
        "records_checked": 2,
        "last_hash": second["hash"],
    }


def test_execution_audit_preserves_explicit_intent_id(tmp_path) -> None:
    audit = ExecutionAuditLog(tmp_path / "audit.jsonl")

    record = audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=1,
        order_type="LMT",
        intent_id="intent-123",
    )

    assert record["intent_id"] == "intent-123"


def test_execution_audit_detects_modified_record(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=1,
        order_type="LMT",
        details={"price": 500.0},
    )
    records = [json.loads(line) for line in path.read_text().splitlines()]
    records[0]["quantity"] = 999.0
    path.write_text(json.dumps(records[0]) + "\n")

    verification = audit.verify()

    assert verification["valid"] is False
    assert "record hash mismatch" in verification["error"]


def test_execution_audit_refuses_append_after_corrupt_tail(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    path.write_text("{not-json}\n")

    with pytest.raises(ValueError, match="tail is corrupt"):
        audit.append(
            event="ORDER_INTENT",
            symbol="SPY",
            side="BUY",
            quantity=1,
            order_type="LMT",
        )


def test_execution_audit_serializes_concurrent_appends(tmp_path) -> None:
    audit = ExecutionAuditLog(tmp_path / "audit.jsonl")

    def append_record(index: int) -> None:
        audit.append(
            event="ORDER_INTENT",
            symbol="SPY",
            side="BUY",
            quantity=index + 1,
            order_type="LMT",
        )

    with ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(append_record, range(40)))

    verification = audit.verify()
    assert verification["valid"] is True
    assert verification["records_checked"] == 40
