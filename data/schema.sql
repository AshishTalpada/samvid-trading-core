-- Trading System V3.0 SQLite Schema (SETO V35.3 — Aligned with brain.py INSERT)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    instrument TEXT,
    direction TEXT,
    pattern TEXT,
    regime TEXT,
    session TEXT,
    entry_price REAL,
    stop_price REAL,
    target_price REAL,
    exit_price REAL,
    shares REAL,
    risk_amount REAL,
    r_r_ratio REAL,
    outcome TEXT,
    pnl_dollars REAL,       -- used by shutdown PnL tally
    net_pnl REAL,           -- used by brain.py INSERT
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
    mfe REAL DEFAULT 0.0,
    mae REAL DEFAULT 0.0,
    intel_snapshot TEXT,    -- neural snapshot (JSON) at trade entry
    unrealized_pnl REAL DEFAULT 0.0
);

CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, instrument TEXT, pattern TEXT,
    base_quality REAL, catalyst_score REAL, entropy_score REAL,
    dhatu_state TEXT, freshness REAL, belief REAL,
    escape_class TEXT, action_taken TEXT, skip_reason TEXT
);

CREATE TABLE IF NOT EXISTS calibration_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, pattern TEXT, instrument TEXT,
    n_trades INTEGER, win_rate REAL,
    win_rate_ci_low REAL, win_rate_ci_high REAL, data_rating TEXT,
    avg_r REAL, avg_hold_hours REAL, regime TEXT,
    crowding_score INTEGER, crowding_status TEXT
);

CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, event_type TEXT, severity TEXT,
    agent TEXT, message TEXT, details TEXT
);

CREATE TABLE IF NOT EXISTS dhatu_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, dhatu_state TEXT, base_modifier REAL,
    freshness_score REAL, final_modifier REAL, instrument TEXT
);

CREATE TABLE IF NOT EXISTS positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER, 
    timestamp TEXT, 
    instrument TEXT,
    shares REAL, 
    entry_price REAL, 
    current_price REAL,
    stop_price REAL, 
    unrealized_pnl REAL, 
    belief REAL, 
    status TEXT,
    broker TEXT,
    account_id TEXT DEFAULT 'UNKNOWN'
);

CREATE INDEX IF NOT EXISTS idx_trades_ts   ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_inst ON trades(instrument);

CREATE TABLE IF NOT EXISTS system_state (
    key TEXT PRIMARY KEY,
    value TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS performance_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
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

-- GAP-44: Evolutionary Architecture
CREATE TABLE IF NOT EXISTS decision_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT,
    features TEXT,
    dhatu_state TEXT,
    trade_id TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS brain_optimization (
    parameter_name TEXT PRIMARY KEY,
    parameter_value TEXT,
    confidence REAL,
    last_updated TEXT
);

-- OHLCV candles (used by data_pipeline)
CREATE TABLE IF NOT EXISTS ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timeframe TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    open REAL, high REAL, low REAL, close REAL, volume REAL,
    UNIQUE(symbol, timeframe, timestamp)
);
CREATE INDEX IF NOT EXISTS idx_ohlcv_sym_tf ON ohlcv(symbol, timeframe, timestamp);

-- VIX snapshots
CREATE TABLE IF NOT EXISTS vix_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    vix REAL
);

-- News ingestion buffer
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    headline TEXT,
    source TEXT,
    sentiment REAL
);

-- Agent D learning trades table
CREATE TABLE IF NOT EXISTS agent_d_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    symbol TEXT,
    pattern TEXT,
    outcome TEXT,
    r_multiple REAL,
    regime TEXT,
    hold_hours REAL
);
