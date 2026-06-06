import json

from execution_audit import ExecutionAuditLog
from scripts import preflight


def test_pid_lock_rejects_duplicate_claim(tmp_path) -> None:
    result = preflight.check_pid_lock(tmp_path)

    assert result.ok is True
    assert "rejected duplicate" in result.detail


def test_dms_tripwire_writes_heartbeat_and_arms_resume_gap(tmp_path) -> None:
    result = preflight.check_dms_tripwire(tmp_path)

    assert result.ok is True
    assert "resume-gap tripwire armed" in result.detail


def test_execution_audit_chain_rejects_tampering(tmp_path) -> None:
    audit_path = tmp_path / "execution_audit.jsonl"
    audit = ExecutionAuditLog(audit_path)
    audit.append(
        event="ORDER_INTENT",
        symbol="SPY",
        side="BUY",
        quantity=1,
        order_type="LMT",
    )
    record = json.loads(audit_path.read_text(encoding="utf-8"))
    record["quantity"] = 2.0
    audit_path.write_text(json.dumps(record) + "\n", encoding="utf-8")

    result = preflight.check_execution_audit_chain(audit_path)

    assert result.ok is False
    assert "hash mismatch" in result.detail


def test_migrations_current_with_sqlite_tracker(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "trading.db"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "0001.example.sql").write_text(
        "CREATE TABLE example (id INTEGER PRIMARY KEY);\n",
        encoding="utf-8",
    )

    from database import migrate

    monkeypatch.setattr(migrate, "apply_migrations", migrate._apply_migrations_sqlite_fallback)

    result = preflight.check_migrations_current(db_path, migrations_dir)

    assert result.ok is True
    assert "1 migration" in result.detail


def test_run_preflight_aggregates_results() -> None:
    def passing_check() -> preflight.PreflightResult:
        return preflight.PreflightResult("pass", True, "ok")

    def failing_check() -> preflight.PreflightResult:
        return preflight.PreflightResult("fail", False, "bad")

    results = preflight.run_preflight([passing_check, failing_check])

    assert [result.ok for result in results] == [True, False]
