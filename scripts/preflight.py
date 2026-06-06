#!/usr/bin/env python3
"""Pre-session safety and evidence preflight checks.

This script is intentionally offline-safe: it does not start the engine, place
orders, connect to brokers, or send Telegram messages. It verifies the safety
primitives that must be reliable before a paper or live session is trusted.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def _ensure_paths() -> None:
    for path in (ROOT, SRC):
        path_str = str(path)
        if path_str not in sys.path:
            sys.path.insert(0, path_str)


@dataclass(frozen=True)
class PreflightResult:
    name: str
    ok: bool
    detail: str
    critical: bool = True


CheckFn = Callable[[], PreflightResult]


def check_pid_lock(lock_dir: Path | None = None) -> PreflightResult:
    """Verify that PID claims are exclusive and cannot be double-acquired."""
    lock_dir = lock_dir or ROOT / "tmp" / "preflight"
    lock_dir.mkdir(parents=True, exist_ok=True)
    pid_file = lock_dir / "main.pid"
    pid_file.unlink(missing_ok=True)

    fd: int | None = None
    try:
        fd = os.open(pid_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(fd, str(os.getpid()).encode("ascii"))
        try:
            os.open(pid_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            return PreflightResult("PID singleton lock", True, "exclusive PID claim rejected duplicate owner")
        return PreflightResult("PID singleton lock", False, "duplicate PID claim was allowed")
    except Exception as exc:
        return PreflightResult("PID singleton lock", False, f"{type(exc).__name__}: {exc}")
    finally:
        if fd is not None:
            os.close(fd)
        pid_file.unlink(missing_ok=True)


def check_dms_tripwire(heartbeat_dir: Path | None = None) -> PreflightResult:
    """Verify DMS heartbeat persistence and resume-gap tripwire arming."""
    _ensure_paths()
    heartbeat_dir = heartbeat_dir or ROOT / "tmp" / "preflight"
    heartbeat_dir.mkdir(parents=True, exist_ok=True)
    heartbeat_file = heartbeat_dir / "task_heartbeats.json"
    heartbeat_file.unlink(missing_ok=True)

    dms_module = None
    original_heartbeat_file = None
    try:
        import dms as dms_module
        from dms import MIN_RESUME_GAP_SECONDS, DMSMonitor

        original_heartbeat_file = dms_module.TASK_HEARTBEAT_FILE
        dms_module.TASK_HEARTBEAT_FILE = heartbeat_file
        monitor = DMSMonitor(bot_token="", chat_id="", timeout=1)
        for agent_id in monitor.critical_agents:
            monitor._last_task_registry_flush = 0.0
            monitor.record_heartbeat(agent_id)

        if not heartbeat_file.exists():
            return PreflightResult("DMS tripwire", False, "heartbeat registry was not written")

        payload = json.loads(heartbeat_file.read_text(encoding="utf-8"))
        heartbeats = payload.get("heartbeats", {})
        missing = sorted(set(monitor.critical_agents) - set(heartbeats))
        if missing:
            return PreflightResult(
                "DMS tripwire",
                False,
                f"heartbeat registry missing critical agents: {', '.join(missing)}",
            )

        threshold = max(float(monitor.timeout), MIN_RESUME_GAP_SECONDS)
        monitor._last_wall_clock_seen = datetime.now(timezone.utc) - timedelta(
            seconds=threshold + 5
        )
        prior_log_disable_level = logging.root.manager.disable
        try:
            logging.disable(logging.CRITICAL)
            fired = monitor.mark_resume_gap_if_needed(source="preflight")
        finally:
            logging.disable(prior_log_disable_level)
        if not fired or monitor.timeout_detected_at is None:
            return PreflightResult("DMS tripwire", False, "resume-gap tripwire did not arm")

        return PreflightResult(
            "DMS tripwire",
            True,
            f"heartbeat registry healthy; resume-gap tripwire armed at >{threshold:.0f}s",
        )
    except Exception as exc:
        return PreflightResult("DMS tripwire", False, f"{type(exc).__name__}: {exc}")
    finally:
        if dms_module is not None and original_heartbeat_file is not None:
            dms_module.TASK_HEARTBEAT_FILE = original_heartbeat_file
        heartbeat_file.unlink(missing_ok=True)


def check_execution_audit_chain(path: Path | None = None) -> PreflightResult:
    """Verify the append-only execution audit hash chain."""
    _ensure_paths()
    from execution_audit import ExecutionAuditLog

    path = path or ROOT / "data" / "execution_audit.jsonl"
    try:
        verification = ExecutionAuditLog(path).verify()
    except Exception as exc:
        return PreflightResult("Execution audit chain", False, f"{type(exc).__name__}: {exc}")

    if not verification.get("valid"):
        return PreflightResult(
            "Execution audit chain",
            False,
            str(verification.get("error", "audit verification failed")),
        )
    return PreflightResult(
        "Execution audit chain",
        True,
        f"verified {verification.get('records_checked', 0)} record(s)",
    )


def _migration_ids_from_db(db_path: Path) -> set[str]:
    if not db_path.exists():
        return set()
    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        if "sovereign_migrations" in tables:
            return {
                row[0]
                for row in conn.execute("SELECT id FROM sovereign_migrations").fetchall()
            }
        if "_yoyo_migration" in tables:
            return {
                row[0]
                for row in conn.execute("SELECT id FROM _yoyo_migration").fetchall()
            }
    return set()


def check_migrations_current(
    db_path: Path | None = None,
    migrations_dir: Path | None = None,
) -> PreflightResult:
    """Apply idempotent migrations and verify every migration is tracked."""
    _ensure_paths()
    from database.migrate import _migration_files, _migration_id, apply_migrations

    db_path = db_path or ROOT / "data" / "trading.db"
    migrations_dir = migrations_dir or ROOT / "migrations"
    try:
        apply_migrations(db_path=db_path, migrations_dir=migrations_dir)
        expected = {_migration_id(path) for path in _migration_files(migrations_dir)}
        applied = _migration_ids_from_db(db_path)
        missing = sorted(expected - applied)
        if missing:
            return PreflightResult(
                "Database migrations",
                False,
                f"pending/untracked migrations after apply: {', '.join(missing)}",
            )
        return PreflightResult(
            "Database migrations",
            True,
            f"{len(expected)} migration(s) applied/tracked",
        )
    except Exception as exc:
        return PreflightResult("Database migrations", False, f"{type(exc).__name__}: {exc}")


def run_preflight(checks: list[CheckFn] | None = None) -> list[PreflightResult]:
    checks = checks or [
        check_pid_lock,
        check_dms_tripwire,
        check_execution_audit_chain,
        check_migrations_current,
    ]
    return [check() for check in checks]


def _print_results(results: list[PreflightResult]) -> None:
    print("=" * 64)
    print(" SOVEREIGN PREFLIGHT")
    print("=" * 64)
    for result in results:
        label = "OK" if result.ok else ("FAIL" if result.critical else "WARN")
        print(f"[{label}] {result.name}: {result.detail}")
    print("=" * 64)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run pre-session safety preflight checks.")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of console text.",
    )
    args = parser.parse_args(argv)

    results = run_preflight()
    if args.json:
        print(json.dumps([result.__dict__ for result in results], indent=2))
    else:
        _print_results(results)

    failed_critical = [result for result in results if result.critical and not result.ok]
    return 1 if failed_critical else 0


if __name__ == "__main__":
    raise SystemExit(main())
