"""
tests/test_migrations.py
Yoyo-migrations integration tests (Phase 3)

Verifies:
  1. Migrations apply cleanly to a fresh database (tmp_path)
  2. All expected tables exist after migration 0001
  3. Columns added by migrations 0002 and 0003 are present
  4. Migrations are idempotent (running twice has no error)
  5. apply_migrations() handles a missing migrations directory gracefully
  6. list_migrations() prints APPLIED status after applying
  7. list_migrations() prints PENDING on a fresh database
  8. Can INSERT a valid trade row after migrations (schema is runtime-compatible)
"""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, "src")

from database.migrate import apply_migrations, list_migrations, _MIGRATIONS_DIR


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tables(db_path: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    names = {row[0] for row in cur.fetchall()}
    conn.close()
    return names


def _columns(db_path: str, table: str) -> set[str]:
    conn = sqlite3.connect(db_path)
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = {row[1] for row in cur.fetchall()}
    conn.close()
    return cols


# ---------------------------------------------------------------------------
# Tests — all use pytest's tmp_path fixture (Windows-safe cleanup)
# ---------------------------------------------------------------------------

def test_migrations_apply_to_fresh_db(tmp_path):
    """Test 1: apply_migrations() succeeds on an empty database."""
    db_path = str(tmp_path / "fresh.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    tables = _tables(db_path)
    assert "trades" in tables
    assert "signals" in tables
    assert "positions" in tables


def test_migration_0001_creates_all_core_tables(tmp_path):
    """Test 2: after migration 0001, all expected tables exist."""
    db_path = str(tmp_path / "core.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    tables = _tables(db_path)
    expected = {
        "trades",
        "signals",
        "calibration_log",
        "system_events",
        "dhatu_readings",
        "positions",
        "performance_summary",
        "decision_snapshots",
        "brain_optimization",
        "ohlcv",
        "vix_data",
        "news",
        "agent_d_trades",
        "system_state",
    }
    missing = expected - tables
    assert not missing, f"Missing tables after migration 0001: {missing}"


def test_migration_0002_adds_kv_columns_to_performance_summary(tmp_path):
    """Test 3a: migration 0002 adds key/value/updated_at to performance_summary."""
    db_path = str(tmp_path / "kv_cols.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    cols = _columns(db_path, "performance_summary")
    assert "key" in cols, "performance_summary.key missing"
    assert "value" in cols, "performance_summary.value missing"
    assert "updated_at" in cols, "performance_summary.updated_at missing"


def test_migration_0003_adds_regime_at_entry_to_trades(tmp_path):
    """Test 3b: migration 0003 adds regime_at_entry to trades."""
    db_path = str(tmp_path / "regime_col.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    cols = _columns(db_path, "trades")
    assert "regime_at_entry" in cols, "trades.regime_at_entry missing"


def test_migrations_are_idempotent(tmp_path):
    """Test 4: running apply_migrations() twice raises no error and tables stay intact."""
    db_path = str(tmp_path / "idempotent.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    # Second call — yoyo tracks applied migrations; nothing should break
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    assert "trades" in _tables(db_path)


def test_apply_migrations_missing_dir_is_graceful(tmp_path):
    """Test 5: missing migrations directory → logs warning, returns without error."""
    db_path = str(tmp_path / "noop.db")
    missing_dir = str(tmp_path / "nonexistent_migrations")
    # Should not raise
    apply_migrations(db_path=db_path, migrations_dir=missing_dir)


def test_list_migrations_shows_applied_status(tmp_path, capsys):
    """Test 6: list_migrations() shows APPLIED for all migrations after apply."""
    db_path = str(tmp_path / "list_test.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    list_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    captured = capsys.readouterr()
    assert "APPLIED" in captured.out
    assert "PENDING" not in captured.out


def test_list_migrations_shows_pending_on_fresh_db(tmp_path, capsys):
    """Test 7: list_migrations() shows PENDING on a fresh database."""
    db_path = str(tmp_path / "pending_test.db")
    # Do NOT apply migrations first
    list_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    captured = capsys.readouterr()
    assert "PENDING" in captured.out


def test_trades_row_insertable_after_migration(tmp_path):
    """Test 8: can INSERT a trade row after migrations (schema matches runtime use)."""
    db_path = str(tmp_path / "insert_test.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO trades "
        "(timestamp, instrument, direction, outcome, broker, trading_mode, regime_at_entry) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2024-01-01T10:00:00+00:00", "AAPL", "LONG", "OPEN", "IBKR", "paper", "TRENDING"),
    )
    conn.commit()
    cur = conn.execute("SELECT COUNT(*) FROM trades")
    count = cur.fetchone()[0]
    conn.close()
    assert count == 1
