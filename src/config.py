import sys
from pathlib import Path

from vault import Vault

PROJECT_PATH = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_PATH / "data"
LOG_DIR = PROJECT_PATH / "logs"

# Ensure crucial directories exist across all platforms
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

IS_WIN = sys.platform == "win32"
DEFAULT_IBKR_PATH = Path("C:/Jts") if IS_WIN else Path("/opt/ibgateway")
TWS_PATH = Vault.get("TWS_PATH", str(DEFAULT_IBKR_PATH))

# SECURITY NOTICE: These constants define hard risk limits.
# Do NOT modify FTMO limits without compliance review.

# Forced Paper Mode (Master Switch)
FORCED_PAPER_MODE = Vault.get("FORCED_PAPER_MODE", "0").strip() == "1"

# Trading Mode Master Selection
VALID_TRADING_MODES = {"paper", "ibkr_paper", "live"}
DEFAULT_TRADING_MODE = "paper"
TRADING_MODE = Vault.get("TRADING_MODE", "ibkr_paper").strip().lower()
if TRADING_MODE not in VALID_TRADING_MODES:
    TRADING_MODE = DEFAULT_TRADING_MODE

# Risk Management
SYSTEM_MAX_RISK = 0.04
CASH_RESERVE = 0.20
BELIEF_EXIT_THRESHOLD = 0.35
BELIEF_CAP = 0.90  # F17: min(0.90, posterior)
VIX_INTRADAY_THRESHOLD = 0.15  # F11
CORRELATION_THRESHOLD = 0.7  # F13

# CRITICAL: These are HARD LIMITS enforced at the compliance layer.
# DO NOT MODIFY without updating agent_c_mt5.py FTMOComplianceLayer
FTMO_DAILY_LIMIT = 0.04  # 4% daily loss limit (safety buffer below FTMO's 5%)
FTMO_DRAWDOWN_LIMIT = 0.08  # 8% maximum drawdown (safety buffer below FTMO's 10%)
MAX_TRADES_PER_DAY = 2  # FTMO challenge limit — DO NOT INCREASE
IBKR_MAX_TRADES_PER_DAY = int(Vault.get("IBKR_MAX_TRADES_PER_DAY", "20"))  # IBKR paper/live
FTMO_ACCOUNT_SIZE = 25000
FTMO_BEST_DAY_RATIO = 2.0 / 3.0

# Commission (Reduced for $500 account agility)
COMMISSION_PER_ROUND_TRIP = float(Vault.get("COMMISSION_PER_ROUND_TRIP", "1.00"))

# Cognitive Memory Cap (FIFO eviction above this count)
COGNITIVE_MEMORY_MAX_ENTRIES = int(Vault.get("COGNITIVE_MEMORY_MAX_ENTRIES", "5000"))

# IBKR
IBKR_PAPER_PORT = 7497
IBKR_LIVE_PORT = 7496
IBKR_HOST = "localhost"
IBKR_CLIENT_ID = 1
IBKR_ACCOUNT_ID = Vault.get("IBKR_ACCOUNT_ID", "")
IBKR_ACCOUNT_TYPE = "margin"

# Dhatu Framework
DHATU_FRESHNESS_HIGH = 0.6
DHATU_FRESHNESS_LOW = 0.3
F16_DECISION = "B"

# Calibration Gates
MIN_TRADES_FOR_CALIBRATION = 200
WALK_FORWARD_MIN_TRADES = 500

# Catalyst Scoring
ESCAPE_SUB_ORBITAL = 0
ESCAPE_ORBITAL = 0
ESCAPE_VELOCITY = 5
UNCONFIRMED_PENALTY = -5

# Sizing Chain
CASH_ACCOUNT_MAX_RATIO = 0.80

# Pattern Lambdas
LAMBDA = {
    "BULL_FLAG": 0.08,
    "CUP_AND_HANDLE": 0.04,
    "CATALYST_PLAY": 0.25,
    "OVERSOLD_BOUNCE": 0.06,
    "SECTOR_SYMPATHY": 0.15,
    "HEAD_SHOULDERS": 0.05,
    "FALLING_WEDGE": 0.07,
    "GAP_FILL": 0.20,
    "DEFAULT": 0.10,
}

# Instrument Tail Multipliers
TAIL = {
    "SPY": 3.2,
    "QQQ": 4.1,
    "MSFT": 4.5,
    "NVDA": 4.8,
    "XAUUSD": 2.8,
    "US100": 4.1,
    "DEFAULT": 4.0,
}

# Volume Thresholds
VOLUME_THRESHOLDS = {
    "SPY": {"normal": 1.10, "elevated": 1.20, "breakout": 1.35},
    "QQQ": {"normal": 1.15, "elevated": 1.30, "breakout": 1.50},
    "MSFT": {"normal": 1.20, "elevated": 1.50, "breakout": 2.00},
    "NVDA": {"normal": 1.25, "elevated": 1.55, "breakout": 2.10},
    "XAUUSD": {"normal": 1.15, "elevated": 1.40, "breakout": 1.80},
    "US100": {"normal": 1.15, "elevated": 1.30, "breakout": 1.50},
}

TRADING_INSTRUMENTS = ["SPY", "QQQ", "MSFT", "NVDA", "XAUUSD", "US100"]

# --- EMERGENCY PANIC SWITCH ---
PANIC_LIQUIDATE = False  # Set to True to force-close all positions on startup

# Capital Calibration: Set to $500 for Live Account Alignment
STARTING_CAPITAL_CAD = float(Vault.get("TOTAL_CAPITAL", "500.0"))
IBKR_ALLOCATION_CAD = STARTING_CAPITAL_CAD * 0.40  # Reduced to 40% for safer margin
FTMO_ALLOCATION_CAD = STARTING_CAPITAL_CAD * 0.49
RISK_PER_TRADE_PCT = 0.005  # 0.5% - Institutional fractional form

# USD -> CAD conversion rate for cross-border asset execution.
USD_CAD_RATE = float(Vault.get("USD_CAD_RATE", "1.35"))

# Quit Criteria
QUIT_AFTER_N_LOSSES = 200
MAX_CHALLENGE_FAILURES = 2
MAX_TOTAL_INVESTMENT_CAD = 30000

# DMS
DMS_HEARTBEAT_INTERVAL = 60
DMS_TIMEOUT_SECONDS = 600  # 10 minutes
DMS_MAX_RETRY_BLIPS = 3  # Number of blips allowed before panic
IBKR_MAX_RECONNECT_ATTEMPTS = 5

DATA_INGESTION_INTERVAL = int(Vault.get("DATA_INGESTION_INTERVAL", "40"))
DATA_MAINTENANCE_INTERVAL = int(Vault.get("DATA_MAINTENANCE_INTERVAL", "300"))
BRAIN_SCAN_INTERVAL = float(Vault.get("BRAIN_SCAN_INTERVAL", "0.05"))

QUESTDB_ENABLED = True  # Activated after successful installation
QUESTDB_HOST = "localhost"
QUESTDB_PORT = 9009  # ILP (Influx Line Protocol over TCP)
QUESTDB_PG_PORT = 8812  # psycopg2 queries for brain OHLCV reads
QUESTDB_USER = Vault.get("QUESTDB_USER", "admin")
QUESTDB_PASSWORD = Vault.get("QUESTDB_PASSWORD", "quest")
QUESTDB_CONNECT_TIMEOUT_SEC = 15.0  # Increased to 15s to resolve failover timeouts


def _validate_config():
    """Ensure critical constants are sane before startup."""
    import logging

    _log = logging.getLogger("config")

    # 1. IBKR Account Validation
    if not IBKR_ACCOUNT_ID and not FORCED_PAPER_MODE:
        _log.warning("⚠️ IBKR_ACCOUNT_ID is empty. System will likely fail on order execution.")

    # 2. Risk Invariant Validation
    if SYSTEM_MAX_RISK > 0.10:
        _log.critical(f"FATAL: SYSTEM_MAX_RISK ({SYSTEM_MAX_RISK}) exceeds safety limit (0.10).")
        sys.exit(1)

    # 3. FTMO Compliance Validation
    if FTMO_DAILY_LIMIT > 0.05:
        _log.error(f"FTMO compliance error: DAILY_LIMIT ({FTMO_DAILY_LIMIT}) must be <= 0.05.")

    # 4. Currency Conversion Sanity
    if USD_CAD_RATE < 1.0 or USD_CAD_RATE > 2.0:
        _log.warning(f"Suspect USD_CAD_RATE ({USD_CAD_RATE}). Expected range: 1.0 - 2.0.")


# Auto-run validation on import
_validate_config()
