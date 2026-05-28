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
  9. Rollback migration 0003 removes regime_at_entry from trades
 10. Rollback migration 0002 removes key/value/updated_at from performance_summary
 11. Full rollback of all migrations removes all core tables
 12. Rollback then re-apply is idempotent (round-trip)
"""

import sqlite3
import sys

sys.path.insert(0, "src")

from database.migrate import _MIGRATIONS_DIR, apply_migrations, list_migrations, rollback_migrations

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


# ---------------------------------------------------------------------------
# Rollback tests — require rollback .sql files to be present
# ---------------------------------------------------------------------------

def test_rollback_0003_removes_regime_at_entry(tmp_path):
    """Test 9: rolling back migration 0003 drops trades.regime_at_entry."""
    import yoyo

    db_path = str(tmp_path / "rb3.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)

    # Confirm column exists before rollback
    assert "regime_at_entry" in _columns(db_path, "trades")

    # Roll back only the last migration (0003)
    db_url = f"sqlite:///{db_path}"
    backend = yoyo.get_backend(db_url)
    migs = yoyo.read_migrations(str(_MIGRATIONS_DIR))
    with backend.lock():
        to_rb = list(backend.to_rollback(migs))
    # to_rb is ordered newest-first; 0003 is first
    assert to_rb[0].id == "0003.add-trades-regime-at-entry"
    backend2 = yoyo.get_backend(db_url)
    with backend2.lock():
        to_rb2 = list(backend2.to_rollback(migs))
        backend2.rollback_one(to_rb2[0])

    assert "regime_at_entry" not in _columns(db_path, "trades"), (
        "regime_at_entry should be gone after rollback of 0003"
    )
    # Earlier tables must still exist
    assert "trades" in _tables(db_path)
    assert "key" in _columns(db_path, "performance_summary")


def test_rollback_0002_removes_kv_columns(tmp_path):
    """Test 10: rolling back migrations 0003+0002 removes kv cols from performance_summary."""
    import yoyo

    db_path = str(tmp_path / "rb2.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)

    assert "key" in _columns(db_path, "performance_summary")

    db_url = f"sqlite:///{db_path}"
    migs = yoyo.read_migrations(str(_MIGRATIONS_DIR))
    # Roll back 0003 then 0002
    backend2 = yoyo.get_backend(db_url)
    with backend2.lock():
        to_rb2 = list(backend2.to_rollback(migs))
        backend2.rollback_one(to_rb2[0])  # 0003
    backend3 = yoyo.get_backend(db_url)
    with backend3.lock():
        to_rb3 = list(backend3.to_rollback(migs))
        backend3.rollback_one(to_rb3[0])  # 0002

    ps_cols = _columns(db_path, "performance_summary")
    assert "key" not in ps_cols, "performance_summary.key should be gone after rollback 0002"
    assert "value" not in ps_cols, "performance_summary.value should be gone after rollback 0002"
    assert "updated_at" not in ps_cols, (
        "performance_summary.updated_at should be gone after rollback 0002"
    )
    # Core tables from 0001 must still be present
    assert "trades" in _tables(db_path)


def test_rollback_all_removes_core_tables(tmp_path):
    """Test 11: rolling back all migrations removes all core tables."""
    db_path = str(tmp_path / "rb_all.db")
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)

    core_tables = {
        "trades", "signals", "positions", "system_state", "ohlcv",
        "performance_summary", "calibration_log", "system_events",
        "dhatu_readings", "decision_snapshots", "brain_optimization",
        "vix_data", "news", "agent_d_trades",
    }
    assert core_tables.issubset(_tables(db_path)), "Core tables must exist before rollback"

    rollback_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)

    # None of the core tables should remain after full rollback
    remaining = core_tables & _tables(db_path)
    assert not remaining, f"Expected all core tables dropped; still present: {remaining}"


def test_rollback_then_reapply_is_idempotent(tmp_path):
    """Test 12: rollback → re-apply leaves the schema intact (round-trip)."""
    db_path = str(tmp_path / "round_trip.db")

    # First apply
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    tables_first = _tables(db_path)
    cols_trades_first = _columns(db_path, "trades")
    cols_ps_first = _columns(db_path, "performance_summary")

    # Full rollback
    rollback_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)

    # Re-apply
    apply_migrations(db_path=db_path, migrations_dir=_MIGRATIONS_DIR)
    tables_second = _tables(db_path)
    cols_trades_second = _columns(db_path, "trades")
    cols_ps_second = _columns(db_path, "performance_summary")

    # Yoyo internal tables differ; compare only user tables
    _yoyo_prefix = ("_yoyo", "yoyo", "sqlite_sequence")
    user_first = {t for t in tables_first if not any(t.startswith(p) for p in _yoyo_prefix)}
    user_second = {t for t in tables_second if not any(t.startswith(p) for p in _yoyo_prefix)}

    assert user_first == user_second, (
        f"Tables differ after round-trip.\nBefore: {user_first}\nAfter:  {user_second}"
    )
    assert cols_trades_first == cols_trades_second, "trades columns differ after round-trip"
    assert cols_ps_first == cols_ps_second, (
        "performance_summary columns differ after round-trip"
    )
