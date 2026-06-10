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


def _safe_float_config(key: str, default: float, minimum: float) -> float:
    try:
        return max(minimum, float(Vault.get(key, str(default))))
    except (TypeError, ValueError):
        return default


# Market observation learning
# Records meaningful scanner observations even when no trade is executed. These rows
# are isolated from realized trade expectancy so they cannot pollute PnL/R stats.
MARKET_OBSERVATION_LEARNING_ENABLED = (
    Vault.get("SOVEREIGN_MARKET_OBSERVATION_LEARNING", "1").strip() == "1"
)
MARKET_OBSERVATION_THROTTLE_SEC = _safe_float_config(
    "SOVEREIGN_MARKET_OBSERVATION_THROTTLE_SEC",
    300.0,
    30.0,
)
MARKET_OBSERVATION_FORWARD_HORIZONS_MIN = tuple(
    int(part.strip())
    for part in Vault.get(
        "SOVEREIGN_MARKET_OBSERVATION_FORWARD_HORIZONS_MIN",
        "5,15,60",
    ).split(",")
    if part.strip().isdigit()
)
if not MARKET_OBSERVATION_FORWARD_HORIZONS_MIN:
    MARKET_OBSERVATION_FORWARD_HORIZONS_MIN = (5, 15, 60)

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

TRADING_INSTRUMENTS = [
    "SPY",
    "QQQ",
    "DIA",
    "IWM",
    "MSFT",
    "AAPL",
    "NVDA",
    "GOOGL",
    "AMZN",
    "META",
    "AVGO",
    "AMD",
    "TSLA",
    "NFLX",
    "COST",
    "GS",
    "JPM",
    "MA",
    "V",
    "WMT",
    "ARM",
    "MU",
    "PLTR",
    "MSTR",
    "COIN",
    "SMCI",
    "XAUUSD",
    "US100",
]

PANIC_LIQUIDATE = False  # Set to True to force-close all positions on startup

# Capital Calibration: Set to $500 for Live Account Alignment
STARTING_CAPITAL_CAD = float(Vault.get("TOTAL_CAPITAL", "500.0"))
# Fraction of the LIVE account value the sizer is allowed to deploy on IBKR.
# Sizing buying power = actual NetLiquidation * this fraction (e.g. $1M paper -> $400k).
# This keeps paper-mode sizing proportional to the real account instead of letting
# the sizer act on the full phantom paper balance.
IBKR_ALLOCATION_FRACTION = float(Vault.get("IBKR_ALLOCATION_FRACTION", "0.40"))
FTMO_ALLOCATION_FRACTION = float(Vault.get("FTMO_ALLOCATION_FRACTION", "0.49"))
IBKR_ALLOCATION_CAD = STARTING_CAPITAL_CAD * IBKR_ALLOCATION_FRACTION
FTMO_ALLOCATION_CAD = STARTING_CAPITAL_CAD * FTMO_ALLOCATION_FRACTION
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
BRAIN_SCAN_INTERVAL = 0.01


def _safe_int_config(key: str, default: int, minimum: int) -> int:
    try:
        return max(minimum, int(Vault.get(key, str(default))))
    except (TypeError, ValueError):
        return default


def _probe_questdb(host: str = "localhost", port: int = 9009, timeout: float = 1.5) -> bool:
    """Quick TCP probe to check if QuestDB ILP port is reachable."""
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resolve_questdb_enabled(env_value: str, host: str, port: int) -> bool:
    normalized = (env_value or "").strip().lower()
    if normalized in ("true", "1", "yes"):
        return True
    if normalized in ("false", "0", "no"):
        return False
    return _probe_questdb(host, port)


QUESTDB_HOST = Vault.get("QUESTDB_HOST", "localhost") or "localhost"
QUESTDB_PORT = _safe_int_config("QUESTDB_PORT", 9009, 1)  # ILP over TCP
QUESTDB_PG_PORT = _safe_int_config("QUESTDB_PG_PORT", 8812, 1)  # PostgreSQL wire
QUESTDB_USER = Vault.get("QUESTDB_USER", "admin")
QUESTDB_PASSWORD = Vault.get("QUESTDB_PASSWORD", "quest")
QUESTDB_CONNECT_TIMEOUT_SEC = _safe_float_config("QUESTDB_CONNECT_TIMEOUT_SEC", 15.0, 0.5)

# Auto-detect QuestDB: honour explicit override from .env/Vault, else probe.
_questdb_env = Vault.get("QUESTDB_ENABLED", "").strip().lower()
QUESTDB_ENABLED = _resolve_questdb_enabled(_questdb_env, QUESTDB_HOST, QUESTDB_PORT)


def _validate_config():
    """Ensure critical constants are sane before startup."""
    import logging

    _log = logging.getLogger("config")

    # 1. IBKR Account Validation
    if not IBKR_ACCOUNT_ID and not FORCED_PAPER_MODE:
        _log.warning(" IBKR_ACCOUNT_ID is empty. System will likely fail on order execution.")

    # 2. Risk Invariant Validation
    if SYSTEM_MAX_RISK > 0.10:
        _log.critical(f"FATAL: SYSTEM_MAX_RISK ({SYSTEM_MAX_RISK}) exceeds safety limit (0.10).")
        raise ValueError(f"SYSTEM_MAX_RISK ({SYSTEM_MAX_RISK}) exceeds hard safety limit (0.10)")

    # 3. FTMO Compliance Validation
    if FTMO_DAILY_LIMIT > 0.05:
        _log.error(f"FTMO compliance error: DAILY_LIMIT ({FTMO_DAILY_LIMIT}) must be <= 0.05.")

    # 4. Currency Conversion Sanity
    if USD_CAD_RATE < 1.0 or USD_CAD_RATE > 2.0:
        _log.warning(f"Suspect USD_CAD_RATE ({USD_CAD_RATE}). Expected range: 1.0 - 2.0.")


# NOTE: Call _validate_config() explicitly after logging is configured (e.g. in main.py).
# Previously ran on import, which could kill the process before logging was ready.
