# ═══════════════════════════════════════════════════════════════════
# UNIFIED TRADING SYSTEM V3.0 — CLEANED SYSTEM CONFIG
# Generated from completed questionnaire — March 21, 2026
# Owner: Ashishkumar | Waterloo, Ontario, Canada
# ═══════════════════════════════════════════════════════════════════
#
# ⚠ 3 BLOCKERS FIXED BEFORE THIS FILE WAS GENERATED:
#   BLOCKER 1: Python 3.14.3 → downgrade to 3.11.9 (see setup below)
#   BLOCKER 2: Project path C:\WINDOWS\system32 → moved to C:\TradingSystem
#   BLOCKER 3: IBKR Regular margin (not RRSP) → config adjusted
#
# ═══════════════════════════════════════════════════════════════════

# ── MACHINE ────────────────────────────────────────────────────────
OS                    = "Windows 11 (Build 10.0.26200)"
PYTHON_TARGET         = "3.11.9"              # Downgraded from 3.14.3
RAM                   = "15.9GB"
CPU                   = "Intel Core i7 (8 cores)"
PROJECT_PATH          = "C:\\TradingSystem"   # Fixed from system32
SQLITE_VERSION        = "3.50.4"
MACHINE_UPTIME        = "24/5"

# ── SECONDARY MACHINE (DMS) ────────────────────────────────────────
DMS_DEVICE            = "iPhone (iOS 16)"
DMS_METHOD            = "telegram_polling"    # iPhone DMS via Telegram bot
# Note: No traditional DMS script needed. iPhone polls Telegram.
# If no heartbeat for 5 min → Telegram bot sends emergency alert.

# ── EDITOR ─────────────────────────────────────────────────────────
EDITOR                = "VS Code + Cursor"    # Cursor detected

# ── EXPERIENCE ─────────────────────────────────────────────────────
PYTHON_LEVEL          = "A-beginner"          # All code: heavily commented
CODE_COMMENTS         = "maximum"             # Every line explained
ERROR_MESSAGES        = "plain english"       # No jargon in errors
IBKR_API_EXP          = False
MT5_API_EXP           = False
DATABASE_EXP          = True                  # Has DB experience
CODE_READABILITY      = "C-logic"             # Understands logic not syntax

# ── ACCOUNTS ───────────────────────────────────────────────────────
IBKR_STATUS           = "open-unfunded"       # Open, needs funding
IBKR_TYPE             = "regular_margin"      # NOT RRSP — affects tax treatment
IBKR_PAPER            = True
IB_GATEWAY            = True
IBKR_PORT             = 7497                  # Paper port
FTMO_STATUS           = "not_started"         # Need to open free trial first
MT5_INSTALLED         = False                 # Install after FTMO trial opens
FINNHUB_KEY           = True
ANTHROPIC_KEY         = True
TELEGRAM_ACCOUNT      = True
TELEGRAM_BOT          = False                 # Need to create via @BotFather
WISE_ACCOUNT          = False                 # Not needed yet

# ── CAPITAL ────────────────────────────────────────────────────────
STARTING_CAPITAL_CAD  = 500
FTMO_ALLOCATION_CAD   = 245
IBKR_ALLOCATION_CAD   = 255
MONTHLY_ADDITION_CAD  = 50
BUFFER                = False
RRSP_AVAILABLE        = False                 # Regular margin account
FTMO_CHALLENGE_SIZE   = 25000                 # $25K (~$155 EUR fee)
TAX_ACCOUNTANT        = False                 # Consult before live trading

# ── DESIGN DECISIONS ───────────────────────────────────────────────
F16_DECISION          = "B"                   # Never override risk management
LOSS_INSTRUMENT       = "Mixed"
LOSS_PERIOD           = "6 months"
LOSS_CAUSE            = "no stops, overtrading"   # Encoded as learning
BUILD_APPROACH        = "B-complete"          # Full system from day one
STARTING_PATTERNS     = "all-16"              # All 16 patterns
TRADING_SCHEDULE      = "full-hours"          # 9AM–4PM ET
RISK_PER_TRADE        = 1.0                   # 1.0% per trade
DASHBOARD             = True                  # Web dashboard on localhost
ALERT_SYSTEM          = "telegram"

# ── QUIT CRITERIA ──────────────────────────────────────────────────
QUIT_AFTER_N_LOSSES   = 200
MAX_CHALLENGE_FAILURES = 2
MAX_TOTAL_INVESTMENT  = 3000                  # CAD
TRUSTED_PERSON        = False                 # Recommended to add one

# ── SYSTEM CONSTANTS (from documentation) ──────────────────────────
SYSTEM_MAX_RISK               = 0.04          # 4% max (below FTMO 5%)
CASH_RESERVE                  = 0.20          # 20% always held
BELIEF_EXIT_THRESHOLD         = 0.35
BELIEF_CAP                    = 0.90          # F17
VIX_INTRADAY_THRESHOLD        = 0.15          # F11
CORRELATION_THRESHOLD         = 0.7           # F13
FTMO_DAILY_LIMIT              = 0.04          # Hard-coded, not from config
FTMO_DRAWDOWN_LIMIT           = 0.08          # Hard-coded
FTMO_MAX_TRADES_PER_DAY       = 2
MIN_TRADES_FOR_CALIBRATION    = 200           # M-04
WALK_FORWARD_MIN_TRADES       = 500           # Before F16 revisit
DHATU_FRESHNESS_HIGH          = 0.6
DHATU_FRESHNESS_LOW           = 0.3
