"""
src/database/migrate.py
Yoyo-migrations runner for the Sovereign Trading System.

Usage (from project root):
    python -m database.migrate                    # apply all pending migrations
    python -m database.migrate --rollback         # roll back the last batch
    python -m database.migrate --list             # show migration status

Programmatic (e.g. from main.py / TradingBrain startup):
    from database.migrate import apply_migrations
    apply_migrations()                            # non-blocking, idempotent
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths (relative to project root)
# ---------------------------------------------------------------------------

# This file lives at  src/database/migrate.py
# → go up two levels to reach project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_MIGRATIONS_DIR = _PROJECT_ROOT / "migrations"
_DEFAULT_DB = _PROJECT_ROOT / "data" / "trading.db"


def apply_migrations(
    db_path: str | Path | None = None,
    migrations_dir: str | Path | None = None,
) -> None:
    """Apply all pending yoyo migrations to the SQLite database.

    This function is idempotent: running it multiple times will only apply
    migrations that have not yet been recorded in the _yoyo_migration table.

    Args:
        db_path: Path to the SQLite file.  Defaults to data/trading.db.
        migrations_dir: Directory containing *.sql migration files.
                        Defaults to <project_root>/migrations/.
    """
    try:
        import yoyo
    except ImportError as exc:
        logger.error(
            "yoyo-migrations not installed. Run: pip install yoyo-migrations. Error: %s", exc
        )
        return

    db_path = Path(db_path or _DEFAULT_DB)
    migrations_dir = Path(migrations_dir or _MIGRATIONS_DIR)

    if not migrations_dir.exists():
        logger.warning("Migrations directory not found: %s — skipping.", migrations_dir)
        return

    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)

    db_url = f"sqlite:///{db_path.as_posix()}"
    logger.info("Running migrations: %s → %s", migrations_dir, db_path)

    try:
        backend = yoyo.get_backend(db_url)
        migrations = yoyo.read_migrations(str(migrations_dir))

        with backend.lock():
            pending = backend.to_apply(migrations)
            if not pending:
                logger.info("No pending migrations.")
                return

            logger.info(
                "Applying %d migration(s): %s",
                len(pending),
                [m.id for m in pending],
            )
            # Apply migrations one at a time so that a "duplicate column name"
            # error (columns already added by schema.sql) is treated as a no-op
            # rather than a hard failure.  All other errors still propagate.
            import sqlite3 as _sqlite3

            for m in pending:
                try:
                    backend.apply_one(m)
                except _sqlite3.OperationalError as col_err:
                    err_msg = str(col_err).lower()
                    if "duplicate column name" in err_msg or "already exists" in err_msg:
                        logger.info(
                            "Migration %s: column already exists — marking as applied (schema is up-to-date).",
                            m.id,
                        )
                        # Mark migration as applied in yoyo's tracking table so
                        # it won't be retried on every startup.
                        try:
                            backend.mark_one(m)
                        except Exception as _mark_err:
                            logger.debug("Could not mark migration %s: %s", m.id, _mark_err)
                    else:
                        raise
            logger.info("All migrations applied successfully.")
    except Exception as exc:
        logger.error("Migration failed: %s", exc, exc_info=True)
        raise


def rollback_migrations(
    db_path: str | Path | None = None,
    migrations_dir: str | Path | None = None,
) -> None:
    """Roll back the last applied migration batch."""
    try:
        import yoyo
    except ImportError as exc:
        logger.error("yoyo-migrations not installed: %s", exc)
        return

    db_path = Path(db_path or _DEFAULT_DB)
    migrations_dir = Path(migrations_dir or _MIGRATIONS_DIR)
    db_url = f"sqlite:///{db_path.as_posix()}"

    backend = yoyo.get_backend(db_url)
    migrations = yoyo.read_migrations(str(migrations_dir))

    with backend.lock():
        applied = backend.to_rollback(migrations)
        if not applied:
            logger.info("Nothing to roll back.")
            return
        logger.warning("Rolling back %d migration(s).", len(applied))
        backend.rollback_migrations(applied)
        logger.info("Rollback complete.")


def list_migrations(
    db_path: str | Path | None = None,
    migrations_dir: str | Path | None = None,
) -> None:
    """Print the status of each migration."""
    try:
        import yoyo
    except ImportError as exc:
        logger.error("yoyo-migrations not installed: %s", exc)
        return

    db_path = Path(db_path or _DEFAULT_DB)
    migrations_dir = Path(migrations_dir or _MIGRATIONS_DIR)
    db_url = f"sqlite:///{db_path.as_posix()}"

    backend = yoyo.get_backend(db_url)
    migrations = yoyo.read_migrations(str(migrations_dir))

    pending_ids = {m.id for m in backend.to_apply(migrations)}
    for m in migrations:
        status = "PENDING" if m.id in pending_ids else "APPLIED "
        print(f"  [{status}] {m.id}")


# ---------------------------------------------------------------------------
# CLI entry-point
# ---------------------------------------------------------------------------

def _main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    parser = argparse.ArgumentParser(description="Sovereign DB migration runner (yoyo)")
    parser.add_argument("--db", help="Path to SQLite database", default=None)
    parser.add_argument("--dir", help="Path to migrations directory", default=None)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--rollback", action="store_true", help="Roll back last batch")
    group.add_argument("--list", action="store_true", help="List migration status")
    args = parser.parse_args()

    if args.rollback:
        rollback_migrations(args.db, args.dir)
    elif args.list:
        list_migrations(args.db, args.dir)
    else:
        apply_migrations(args.db, args.dir)


if __name__ == "__main__":
    _main()
