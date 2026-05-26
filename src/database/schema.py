"""
Database schema management for the Sovereign Trading System.

Extracted from TradingSystem (main.py) to enforce Single Responsibility Principle.
All table creation, index definitions, and migration steps live here.
"""

import logging
import sqlite3

logger = logging.getLogger(__name__)


def ensure_runtime_telemetry_schema(cursor: sqlite3.Cursor) -> None:
    """Ensure dashboard/API telemetry tables are present and readable."""
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            event_type TEXT,
            severity TEXT,
            agent TEXT,
            message TEXT,
            details TEXT
        );
        CREATE TABLE IF NOT EXISTS dhatu_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            dhatu_state TEXT,
            base_modifier REAL,
            freshness_score REAL,
            final_modifier REAL,
            instrument TEXT
        );
        CREATE TABLE IF NOT EXISTS performance_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            total_trades INTEGER DEFAULT 0,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            win_rate REAL DEFAULT 0.0,
            total_r REAL DEFAULT 0.0,
            max_drawdown REAL DEFAULT 0.0,
            daily_pnl REAL DEFAULT 0.0,
            broker TEXT,
            entropy_score REAL DEFAULT 0.0
        );
    """)

    cursor.execute("PRAGMA table_info(performance_summary)")
    performance_cols = {row[1] for row in cursor.fetchall()}
    for column, decl in {
        "key": "TEXT",
        "value": "TEXT",
        "updated_at": "TIMESTAMP",
    }.items():
        if column not in performance_cols:
            cursor.execute(f"ALTER TABLE performance_summary ADD COLUMN {column} {decl}")

    cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_events_ts ON system_events(timestamp)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dhatu_readings_ts ON dhatu_readings(timestamp)")


def create_basic_schema(db_conn: sqlite3.Connection) -> None:
    """Create minimal schema if schema.sql doesn't exist."""
    if db_conn is None:
        return
    cursor = db_conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS system_state (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS ohlcv (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TIMESTAMP NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            timeframe TEXT,
            source TEXT,
            UNIQUE(symbol, timestamp, timeframe, source)
        );
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            instrument TEXT,
            direction TEXT,
            pattern TEXT,
            regime TEXT,
            session TEXT DEFAULT 'RTH',
            entry_price REAL,
            stop_price REAL,
            target_price REAL,
            exit_price REAL,
            shares REAL,
            risk_amount REAL,
            r_r_ratio REAL,
            outcome TEXT,
            pnl_dollars REAL,
            r_multiple REAL,
            hold_hours REAL,
            catalyst_score REAL,
            dhatu_state TEXT,
            belief_at_entry REAL,
            belief_at_exit REAL,
            broker TEXT,
            account_id TEXT DEFAULT 'UNKNOWN',
            trading_mode TEXT DEFAULT 'paper',
            notes TEXT,
            commission REAL DEFAULT 0.0,
            slippage REAL DEFAULT 0.0,
            net_pnl REAL DEFAULT 0.0,
            mfe REAL DEFAULT 0.0,
            mae REAL DEFAULT 0.0,
            intel_snapshot TEXT,
            unrealized_pnl REAL DEFAULT 0.0
        );
        CREATE TABLE IF NOT EXISTS positions (
            symbol TEXT PRIMARY KEY,
            quantity REAL NOT NULL,
            avg_price REAL,
            broker TEXT,
            account_id TEXT DEFAULT 'UNKNOWN',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            confidence REAL,
            metadata TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS vix_data (
            timestamp TIMESTAMP NOT NULL,
            value REAL,
            UNIQUE(timestamp)
        );
        CREATE INDEX IF NOT EXISTS idx_ohlcv_symbol_time
            ON ohlcv(symbol, timestamp);
        CREATE INDEX IF NOT EXISTS idx_trades_symbol
            ON trades(symbol);
        CREATE INDEX IF NOT EXISTS idx_signals_symbol_time
            ON signals(symbol, timestamp);
        CREATE INDEX IF NOT EXISTS idx_vix_time
            ON vix_data(timestamp);
    """)

    cursor.close()
    logger.info("✓ Basic schema created")
