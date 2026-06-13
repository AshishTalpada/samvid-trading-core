import json
import sqlite3

from execution_audit import ExecutionAuditLog
from scripts.startup_validation import validate_execution_audit, validate_paper_performance_baseline


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


def test_startup_validation_warns_when_paper_baseline_is_missing(tmp_path) -> None:
    path = tmp_path / "trading.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT)")
    conn.close()

    assert validate_paper_performance_baseline(str(path)) == [
        "Paper performance baseline is not established"
    ]


def test_startup_validation_accepts_valid_paper_baseline(tmp_path) -> None:
    path = tmp_path / "trading.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE system_state (key TEXT PRIMARY KEY, value TEXT)")
        conn.execute(
            "INSERT INTO system_state VALUES (?, ?)",
            ("paper_performance_baseline", '{"min_trade_id": 42, "reason": "test"}'),
        )
    conn.close()

    assert validate_paper_performance_baseline(str(path)) == []
