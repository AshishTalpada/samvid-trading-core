#!/usr/bin/env python3
"""
Startup Validation Script — Run before starting the trading system.

Checks critical imports, database schema, environment, and agent wiring
without requiring live broker connections.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path


def _ensure_paths() -> None:
    root = Path(__file__).resolve().parent.parent
    src = root / "src"
    for p in (str(root), str(src)):
        if p not in sys.path:
            sys.path.insert(0, p)


def validate_imports() -> list[str]:
    """Check that all critical modules import without errors."""
    _ensure_paths()
    required = [
        "brain",
        "brain_state",
        "agent_a",
        "agent_b",
        "agent_c_ibkr",
        "agent_c_mt5",
        "agent_d",
        "agent_e",
        "dms",
        "exit_intelligence",
        "mind_ultrathink",
        "data_pipeline",
        "config",
        "trading_state",
        "safety",
    ]
    failed: list[str] = []
    for mod in required:
        try:
            __import__(mod)
        except Exception as exc:
            failed.append(f"{mod}: {type(exc).__name__}: {exc}")
    return failed


def validate_db_schema() -> list[str]:
    """Check that the SQLite database has required tables."""
    _ensure_paths()
    import sqlite3

    required_tables = {
        "trades",
        "signals",
        "positions",
        "performance_summary",
        "system_state",
        "ohlcv",
        "vix_data",
        "news",
        "agent_d_trades",
        "calibration_log",
    }
    db_path = Path("data/trading.db")
    if not db_path.exists():
        return ["Database file not found: data/trading.db"]
    missing: list[str] = []
    try:
        conn = sqlite3.connect(str(db_path), timeout=5.0)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row[0] for row in cursor.fetchall()}
        conn.close()
        for t in required_tables:
            if t not in tables:
                missing.append(f"Missing table: {t}")
    except Exception as exc:
        missing.append(f"DB schema check failed: {type(exc).__name__}: {exc}")
    return missing


def validate_env() -> list[str]:
    """Check that required environment variables or Vault entries exist."""
    from vault import Vault

    warnings: list[str] = []
    try:
        if not Vault.get("TELEGRAM_BOT_TOKEN"):
            warnings.append("TELEGRAM_BOT_TOKEN not in Vault")
    except Exception:
        warnings.append("TELEGRAM_BOT_TOKEN not in Vault")

    # Use Vault.get so that .env-loaded values and Windows Vault are both checked.
    mode = Vault.get("TRADING_MODE", "") or os.environ.get("TRADING_MODE", "")
    if not mode:
        warnings.append("TRADING_MODE not set (defaulting to paper) — SAFE")
    return warnings


def validate_telegram_alerting() -> list[str]:
    """Check that Telegram alerting is configured (advisory — not required to start)."""
    from vault import Vault

    # [Telegram Alerting]
    _tg_token = Vault.get("TELEGRAM_BOT_TOKEN", "")
    if not _tg_token:
        return ["TELEGRAM_BOT_TOKEN not set — no live alerts on drawdown/halt events"]
    return []


def validate_agent_wiring() -> list[str]:
    """Check that advisory agents can be instantiated."""
    _ensure_paths()
    failed: list[str] = []
    agents = [
        ("contrarian_agent", "ContrarianAgent"),
        ("chaos_agent", "ChaosAgent"),
        ("contagion_sentinel", "ContagionSentinel"),
        ("audit_agent", "AuditAgent"),
    ]
    for mod_name, cls_name in agents:
        try:
            mod = __import__(mod_name)
            cls = getattr(mod, cls_name, None)
            if cls is None:
                failed.append(f"{mod_name}.{cls_name} not found")
            else:
                cls()  # try instantiate
        except Exception as exc:
            failed.append(f"{mod_name}.{cls_name}: {type(exc).__name__}: {exc}")
    return failed


def validate_brain_state() -> list[str]:
    """Check that brain state primitives work correctly."""
    _ensure_paths()
    failed: list[str] = []
    prior_disable_level = logging.root.manager.disable
    try:
        from brain_state import ConsecutiveLossTracker, DrawdownLadder, DrawdownLevel
        from trading_state import TradingStateManager

        prior_state = TradingStateManager._state
        prior_reason = TradingStateManager._reason
        logging.disable(logging.CRITICAL)
        try:
            dd = DrawdownLadder(account_type="ibkr", peak_equity=1000.0)
            level = dd.update(equity=870.0)
            assert level.name == "RED", f"Expected RED at 13% DD on $1K, got {level.name}"

            dd2 = DrawdownLadder(account_type="ibkr", peak_equity=5000.0)
            level2 = dd2.update(equity=4350.0)
            assert level2.name == "YELLOW", f"Expected YELLOW at 13% DD on $5K, got {level2.name}"
        finally:
            TradingStateManager._state = prior_state
            TradingStateManager._reason = prior_reason
            logging.disable(prior_disable_level)

        tracker = ConsecutiveLossTracker()
        for _ in range(10):
            tracker.record_outcome(is_win=True)
        mod = tracker.get_size_modifier()
        assert mod <= 1.15, f"Win streak modifier {mod} exceeds 1.15 cap"
    except AssertionError as exc:
        failed.append(f"brain_state validation: {exc}")
    except Exception as exc:
        failed.append(f"brain_state validation: {type(exc).__name__}: {exc}")
    return failed


def validate_execution_audit(path: str = "data/execution_audit.jsonl") -> list[str]:
    """Refuse startup validation when the persisted execution audit chain is corrupt."""
    _ensure_paths()
    from execution_audit import ExecutionAuditLog

    verification = ExecutionAuditLog(path).verify()
    if verification["valid"]:
        return []
    return [f"Execution audit chain failed verification: {verification.get('error', 'unknown')}"]


def validate_paper_performance_baseline(path: str = "data/trading.db") -> list[str]:
    """Surface missing or malformed post-repair paper measurement boundaries."""
    _ensure_paths()
    from paper_performance import load_performance_baseline

    try:
        baseline = load_performance_baseline(path)
    except Exception as exc:
        return [f"Paper performance baseline is invalid: {type(exc).__name__}: {exc}"]
    if baseline is None:
        return ["Paper performance baseline is not established"]
    return []


def main() -> int:
    os.environ.setdefault("SOVEREIGN_SKIP_PID_CHECK", "1")
    os.environ.setdefault("ALLOW_FORCE_LIVE", "0")

    print("=" * 60)
    print(" SOVEREIGN STARTUP VALIDATION")
    print("=" * 60)

    checks = [
        ("Critical Imports", validate_imports, True),
        ("Database Schema", validate_db_schema, True),
        ("Environment / Vault", validate_env, False),
        ("Telegram Alerting", validate_telegram_alerting, False),
        ("Agent Wiring", validate_agent_wiring, True),
        ("Brain State Primitives", validate_brain_state, True),
        ("Execution Audit Chain", validate_execution_audit, True),
        ("Paper Performance Baseline", validate_paper_performance_baseline, False),
    ]

    total_failures = 0
    for name, check_fn, is_critical in checks:
        print(f"\n[{name}]")
        errors = check_fn()
        if errors:
            for err in errors:
                if is_critical:
                    total_failures += 1
                    print(f"  FAIL: {err}")
                else:
                    print(f"  WARN: {err}")
        else:
            print("  OK")

    print("\n" + "=" * 60)
    if total_failures == 0:
        print(" ALL CHECKS PASSED — System is ready to start.")
        print("=" * 60)
        return 0
    else:
        print(f" {total_failures} CHECK(S) FAILED — Fix before starting.")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
