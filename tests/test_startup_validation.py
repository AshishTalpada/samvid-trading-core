import json

from execution_audit import ExecutionAuditLog
from scripts.startup_validation import validate_execution_audit


def test_startup_validation_accepts_clean_execution_audit(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=1,
        order_type="LMT",
    )

    assert validate_execution_audit(str(path)) == []


def test_startup_validation_rejects_tampered_execution_audit(tmp_path) -> None:
    path = tmp_path / "audit.jsonl"
    audit = ExecutionAuditLog(path)
    audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=1,
        order_type="LMT",
    )
    record = json.loads(path.read_text())
    record["quantity"] = 999.0
    path.write_text(json.dumps(record) + "\n")

    errors = validate_execution_audit(str(path))

    assert errors
    assert "failed verification" in errors[0]
