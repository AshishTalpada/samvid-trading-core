# pyre-ignore-all-errors
"""
UNIFIED TRADING SYSTEM V3.0 - AUTONOMOUS ORCHESTRATOR v2
=========================================================
No CrewAI. Direct API calls only. Stays within 30K TPM rate limit.

Phase 1: Generates config/registry/schema directly (zero AI tokens)
Phase 2: Calls AI directly for each file with small focused prompts

Models:
  claude-sonnet-4-5  -> Agents A, Brain, DMS, Pipeline, Main, Tests
  claude-opus-4-5    -> Agent B (Dhatu - needs deep reasoning)
  gpt-4o             -> Agent C (Risk/FTMO - precise numerics)
  gemini-2.0-flash   -> Agent D (Learning/Calibration)

Usage: python orchestrator.py
"""

import os, json, time, sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv # pyre-ignore[21]

load_dotenv(override=True)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
OPENAI_API_KEY    = os.getenv("OPENAI_API_KEY")
GOOGLE_API_KEY    = os.getenv("GOOGLE_API_KEY")

ROOT      = Path(__file__).parent
SRC_DIR   = ROOT / "src"
TESTS_DIR = ROOT / "tests"
OUTPUTS   = ROOT / "outputs"
LOGS_DIR  = ROOT / "logs"
DATA_DIR  = ROOT / "data"
DOC1      = ROOT / "EVERYTHING_FINAL.md"
DOC2      = ROOT / "UNIFIED_V3_WITH_SIMULATION.md"

for d in [SRC_DIR, TESTS_DIR, OUTPUTS, LOGS_DIR, DATA_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# =============================================================================
# HELPERS
# =============================================================================

def pace(s=65):
    """Wait between AI calls to respect 30K tokens/minute rate limit."""
    print(f"\n  Waiting {s}s (rate limit cooldown)...\n")
    time.sleep(s)


def doc_section(keywords, max_lines=300):
    """Return only lines matching keywords from primary doc. Keeps context tiny."""
    if not DOC1.exists():
        return "Documentation not found."
    lines = DOC1.read_text(encoding="utf-8").split("\n")
    hits  = [l for l in lines if any(k.lower() in l.lower() for k in keywords)]
    return "\n".join(hits[:max_lines]) # pyre-ignore


def extract_code(text):
    """Pull Python code out of AI response."""
    if "```python" in text:
        s = text.find("```python") + 9
        e = text.find("```", s)
        if e > s:
            return text[s:e].strip()
    if "```" in text:
        s = text.find("```") + 3
        n = text.find("\n", s)
        e = text.find("```", n)
        if e > n:
            return text[n:e].strip()
    return text.strip()


def call_claude(model, prompt, max_tokens=8000):
    """Direct Anthropic API call with retry on rate limit."""
    import anthropic # pyre-ignore[21]
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    for attempt in range(4):
        try:
            msg = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return msg.content[0].text
        except anthropic.RateLimitError:
            wait = 70 * (attempt + 1)
            print(f"    Rate limit - waiting {wait}s...")
            time.sleep(wait)
        except Exception as e:
            print(f"    Claude error: {e}")
            raise
    raise RuntimeError("Claude: max retries exceeded")


def call_openai(prompt, max_tokens=8000):
    """Direct OpenAI API call with retry."""
    from openai import OpenAI # pyre-ignore[21]
    client = OpenAI(api_key=OPENAI_API_KEY)
    for attempt in range(4):
        try:
            r = client.chat.completions.create(
                model="gpt-4o",
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            )
            return r.choices[0].message.content
        except Exception as e:
            if "429" in str(e):
                wait = 70 * (attempt + 1)
                print(f"    Rate limit - waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("OpenAI: max retries exceeded")


def call_gemini(prompt):
    """Direct Google Gemini API call with retry."""
    from google import genai # pyre-ignore[21]
    client = genai.Client(api_key=GOOGLE_API_KEY)
    for attempt in range(4):
        try:
            r = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt
            )
            return r.text
        except Exception as e:
            err = str(e).lower()
            if "429" in err or "quota" in err or "rate" in err:
                wait = 70 * (attempt + 1)
                print(f"    Rate limit - waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("Gemini: max retries exceeded")


def write_src(filename, code):
    path = SRC_DIR / filename
    path.write_text(code, encoding="utf-8")
    lines = len(code.split("\n"))
    print(f"    OK src/{filename} ({lines} lines)")


def write_tests(filename, code):
    path = TESTS_DIR / filename
    path.write_text(code, encoding="utf-8")
    lines = len(code.split("\n"))
    print(f"    OK tests/{filename} ({lines} lines)")


def check():
    """Verify all prerequisites before starting."""
    print("\n" + "="*62)
    print("  UNIFIED TRADING SYSTEM V3.0 - PREREQUISITE CHECK")
    print("="*62)
    ok = True
    print("\n  API Keys:")
    for name, val in [
        ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
        ("OPENAI_API_KEY",    OPENAI_API_KEY),
        ("GOOGLE_API_KEY",    GOOGLE_API_KEY),
    ]:
        good = bool(val and len(val) > 10)
        print(f"    {'OK' if good else 'MISSING'} {name}")
        if not good:
            ok = False
    print("\n  Documentation:")
    for doc in [DOC1, DOC2]:
        exists = doc.exists()
        size   = f"{doc.stat().st_size // 1024}KB" if exists else "MISSING"
        print(f"    {'OK' if exists else 'MISSING'} {doc.name} ({size})")
        if not exists:
            ok = False
    print()
    return ok


# =============================================================================
# PHASE 1: DIRECT GENERATION - zero AI tokens used
# =============================================================================

def phase1():
    """Generate config.py, task_registry.json, schema.sql directly."""
    print("  PHASE 1: Direct file generation (zero API calls)")

    config_code = '''"""
Trading System V3.0 - System Constants
All values from EVERYTHING_FINAL.md and UNIFIED_V3_WITH_SIMULATION.md
"""

# Risk Management
SYSTEM_MAX_RISK           = 0.04
CASH_RESERVE              = 0.20
BELIEF_EXIT_THRESHOLD     = 0.35
BELIEF_CAP                = 0.90   # F17: min(0.90, posterior)
VIX_INTRADAY_THRESHOLD    = 0.15   # F11
CORRELATION_THRESHOLD     = 0.7    # F13

# FTMO Limits - HARD-CODED, NEVER CHANGE
FTMO_DAILY_LIMIT          = 0.04
FTMO_DRAWDOWN_LIMIT       = 0.08
FTMO_MAX_TRADES_PER_DAY   = 2
FTMO_ACCOUNT_SIZE         = 25000
FTMO_BEST_DAY_RATIO       = 2 / 3

# IBKR
IBKR_PAPER_PORT           = 7497
IBKR_LIVE_PORT            = 7496
IBKR_HOST                 = "127.0.0.1"
IBKR_CLIENT_ID            = 1
IBKR_ACCOUNT_TYPE         = "margin"

# Dhatu Framework
DHATU_FRESHNESS_HIGH      = 0.6
DHATU_FRESHNESS_LOW       = 0.3
F16_DECISION              = "B"

# Calibration Gates (M-04)
MIN_TRADES_FOR_CALIBRATION = 200
WALK_FORWARD_MIN_TRADES    = 500

# F3 Catalyst Scoring
ESCAPE_SUB_ORBITAL        = -12
ESCAPE_ORBITAL            = 0
ESCAPE_VELOCITY           = 5
UNCONFIRMED_PENALTY       = -15

# F6 Sizing Chain
CASH_ACCOUNT_MAX_RATIO    = 0.80

# Pattern Lambdas (M-06)
LAMBDA = {
    "BULL_FLAG": 0.08, "CUP_AND_HANDLE": 0.04, "CATALYST_PLAY": 0.25,
    "OVERSOLD_BOUNCE": 0.06, "SECTOR_SYMPATHY": 0.15,
    "HEAD_SHOULDERS": 0.05, "FALLING_WEDGE": 0.07,
    "GAP_FILL": 0.20, "DEFAULT": 0.10,
}

# Instrument Tail Multipliers (M-07)
TAIL = {
    "SPY": 3.2, "QQQ": 4.1, "IWM": 4.5, "DIA": 3.5,
    "XLK": 3.8, "XLF": 3.6, "XAUUSD": 2.8, "US100": 4.1, "DEFAULT": 4.0,
}

# Volume Thresholds (F5)
VOLUME_THRESHOLDS = {
    "SPY":    {"normal": 1.10, "elevated": 1.20, "breakout": 1.35},
    "QQQ":    {"normal": 1.15, "elevated": 1.30, "breakout": 1.50},
    "IWM":    {"normal": 1.20, "elevated": 1.50, "breakout": 2.00},
    "DIA":    {"normal": 1.10, "elevated": 1.25, "breakout": 1.40},
    "XLK":    {"normal": 1.15, "elevated": 1.35, "breakout": 1.60},
    "XLF":    {"normal": 1.20, "elevated": 1.40, "breakout": 1.70},
    "XAUUSD": {"normal": 1.15, "elevated": 1.40, "breakout": 1.80},
    "US100":  {"normal": 1.15, "elevated": 1.30, "breakout": 1.50},
}

# Instruments
TRADING_INSTRUMENTS = ["SPY", "QQQ", "IWM", "DIA", "XLK", "XLF", "XAUUSD", "US100"]

# Capital
STARTING_CAPITAL_CAD    = 500
IBKR_ALLOCATION_CAD     = 255
FTMO_ALLOCATION_CAD     = 245
RISK_PER_TRADE_PCT      = 1.0

# Quit Criteria
QUIT_AFTER_N_LOSSES       = 200
MAX_CHALLENGE_FAILURES    = 2
MAX_TOTAL_INVESTMENT_CAD  = 3000

# DMS
DMS_HEARTBEAT_INTERVAL  = 60
DMS_TIMEOUT_SECONDS     = 300
'''
    write_src("config.py", config_code)

    registry = {
        "created": str(datetime.now()),
        "tasks": {
            "T01": {"file": "src/config.py",             "done": True,  "agent": "direct"},
            "T02": {"file": "src/agent_a.py",            "done": False, "agent": "claude-sonnet-4-5"},
            "T03": {"file": "src/agent_b.py",            "done": False, "agent": "claude-opus-4-5"},
            "T04": {"file": "src/agent_c_ibkr.py",       "done": False, "agent": "gpt-4o"},
            "T05": {"file": "src/agent_c_mt5.py",        "done": False, "agent": "gpt-4o"},
            "T06": {"file": "src/agent_d.py",            "done": False, "agent": "gemini-2.0-flash"},
            "T07": {"file": "src/brain.py",              "done": False, "agent": "claude-sonnet-4-5"},
            "T08": {"file": "src/exit_intelligence.py",  "done": False, "agent": "claude-sonnet-4-5"},
            "T09": {"file": "src/dms.py",                "done": False, "agent": "claude-sonnet-4-5"},
            "T10": {"file": "src/data_pipeline.py",      "done": False, "agent": "claude-sonnet-4-5"},
            "T11": {"file": "data/schema.sql",           "done": True,  "agent": "direct"},
            "T12": {"file": "src/main.py",               "done": False, "agent": "claude-sonnet-4-5"},
            "T13": {"file": "tests/test_integration.py", "done": False, "agent": "claude-sonnet-4-5"},
        }
    }
    (OUTPUTS / "task_registry.json").write_text(json.dumps(registry, indent=2))
    print(f"    OK outputs/task_registry.json (13 tasks)")

    schema = """-- Trading System V3.0 SQLite Schema
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL, instrument TEXT, direction TEXT, pattern TEXT,
    regime TEXT, session TEXT, entry_price REAL, stop_price REAL,
    target_price REAL, exit_price REAL, shares REAL, risk_amount REAL,
    r_r_ratio REAL, outcome TEXT, pnl_dollars REAL, r_multiple REAL,
    hold_hours REAL, catalyst_score REAL, dhatu_state TEXT,
    belief_at_entry REAL, belief_at_exit REAL,
    broker TEXT, trading_mode TEXT DEFAULT 'paper', notes TEXT
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
    trade_id INTEGER, timestamp TEXT, instrument TEXT,
    shares REAL, entry_price REAL, current_price REAL,
    stop_price REAL, unrealized_pnl REAL, belief REAL, status TEXT
);
CREATE INDEX IF NOT EXISTS idx_trades_ts   ON trades(timestamp);
CREATE INDEX IF NOT EXISTS idx_trades_inst ON trades(instrument);
"""
    (DATA_DIR / "schema.sql").write_text(schema)
    print(f"    OK data/schema.sql")
    print("\n  Phase 1 complete - 3 files, zero API calls\n")


# =============================================================================
# PHASE 2: AI CODE GENERATION
# =============================================================================

def build_agent_a():
    ctx = doc_section(["Agent A", "Bull Flag", "Head and Shoulders",
                       "Oversold Bounce", "Sector Sympathy", "Falling Wedge",
                       "entropy", "escape velocity", "M-01", "M-06", "F2"])
    ctx = ctx[:2000] # type: ignore
    p = f"""Write src/agent_a.py for a trading system.
Doc context: {ctx} # pyre-ignore

Constants: FTMO_DAILY_LIMIT=0.04, FTMO_DRAWDOWN_LIMIT=0.08,
FTMO_MAX_TRADES_PER_DAY=2, UNCONFIRMED_PENALTY=-15,
Escape: sub_orbital=-12, orbital=0, escape=+5

Write these 6 classes (complete Python, type-annotated, commented):
1. ContinuousBudgetMonitor: attrs daily_loss_pct, drawdown_pct, trades_today;
   is_trading_allowed()->bool; best_day_rule(today, others)->bool (today<=2/3*sum(others))
2. PatternResult(dataclass): name,confidence,entry,stop,target,r_r_ratio,confirmed,lambda_val
3. PatternDetector: detect_bull_flag,detect_head_and_shoulders,detect_falling_wedge,
   detect_oversold_bounce,detect_sector_sympathy,detect_gap_fill (all take pandas DataFrame)
4. SignalEntropyCalculator: signal_entropy(p_before,p_after)->float; entropy_modifier(base,score)->int
5. EscapeVelocityClassifier: classify(price,resistances)->str; modifier(cls)->int
6. MultiTimeframeAligner: check_alignment(symbol,timeframes)->float

Complete Python file only."""
    code = extract_code(call_claude("claude-sonnet-4-5", p))
    write_src("agent_a.py", code)


def build_agent_b():
    ctx = doc_section(["Dhatu", "sutra", "Bayesian", "belief", "catalyst",
                       "ABHAVA", "decay", "F3", "F8", "F17", "F18", "freshness"])
    ctx = ctx[:2000] # type: ignore
    p = f"""Write src/agent_b.py for a trading system.
Doc context: {ctx} # pyre-ignore

CRITICAL: F3 ORDER: base->modifiers->decay->dhatu*freshness->escape->compare
F17: belief=min(0.90,posterior); F18: dhatu_modifier=base*freshness
EXIT if belief<0.35, ADD if >0.80

Write these 6 classes (complete Python, type-annotated, commented):
1. DhatuState(dataclass): name,state_type,base_modifier,freshness_score
2. DhatuClassifier: classify(market_data)->DhatuState (8 states: Vriddhi,Kshaya,
   Sthira,Chala,Abhava,Samyoga,Viyoga,Sthiti); sutra_freshness_score(age_hours)->float;
   dhatu_modifier(base,freshness)->float
3. BayesianBeliefTracker: __init__(prior); update(evidence_type,value)->str; current_belief property
   F8 likelihoods: price_toward_small=0.58, medium=0.72, large=0.85;
   price_against_small=0.45, medium=0.30; volume_confirming=0.68; vix_declining=0.62
4. ABHAVADetector: detect(history)->bool
5. InformationDecayModel: decay_factor(age_hours,high_entropy)->float
6. CatalystScorer: score(base_quality,modifiers,age_hours,dhatu_state,escape_class,budget_min)
   ->tuple[float,bool] - MUST follow F3 order with comments for each step

Complete Python file only."""
    code = extract_code(call_claude("claude-opus-4-5", p))
    write_src("agent_b.py", code)


def build_agent_c_ibkr():
    ctx = doc_section(["Kelly", "F6", "IBKR", "fat tail", "gap risk",
                       "Black Swan", "VIX", "correlation", "M-03", "M-07", "F7", "F11", "F13"])
    ctx = ctx[:2000] # type: ignore
    p = f"""Write src/agent_c_ibkr.py for a trading system.
Doc context: {ctx} # pyre-ignore

TAIL: SPY=3.2,QQQ=4.1,IWM=4.5,DIA=3.5,XLK=3.8,XLF=3.6,XAUUSD=2.8,US100=4.1
SYSTEM_MAX_RISK=0.04, CASH_ACCOUNT_MAX_RATIO=0.80

Write these 8 classes (complete Python, type-annotated, commented):
1. IBKRConnection: connect(port,cid)->bool; get_account_value()->float;
   place_order(sym,dir,shares,type)->int; cancel_order(id); get_positions()->list
2. KellySizer: calculate(win_prob,rr_ratio,balance)->float (half-kelly, cap 4%)
3. FatTailRiskAdjuster: adjust(normal_risk,instrument)->float
4. PositionSizingChain: calculate(...)->dict with step1..step8_shares
   ALL 8 STEPS: kelly->cap->cash_acct->gap_risk->chaos_time->fat_tail->session->shares
5. VIXProtocol: monitor_intraday(vix_now,vix_open,vix_entry)->str
6. CorrelationCascade: on_exit(exited,all_positions)->list
7. BlackSwanProtocol: check(vix,drawdown)->str (NONE/TIGHTEN/FREEZE)
8. PortfolioGuard: enforce_cash_reserve(balance,pos_value)->bool

Complete Python file only."""
    code = extract_code(call_openai(p))
    write_src("agent_c_ibkr.py", code)


def build_agent_c_mt5():
    ctx = doc_section(["MT5", "FTMO", "MetaTrader", "Best Day", "Prague",
                       "lot", "compliance", "funded", "Swing"])
    ctx = ctx[:2000] # type: ignore
    p = f"""Write src/agent_c_mt5.py for a trading system.
Doc context: {ctx} # pyre-ignore

FTMO class attributes HARD-CODED (literal values, NOT imported):
DAILY_LIMIT=0.04, DRAWDOWN_LIMIT=0.08, MAX_TRADES=2

Write these 4 classes (complete Python, type-annotated, commented):
1. MT5Connection: connect(login,pw,server)->bool; get_account_info()->dict;
   place_order(sym,dir,vol,sl,tp)->int; close_position(ticket)->bool; get_open_positions()->list
2. FTMOComplianceLayer (attrs: DAILY_LIMIT=0.04, DRAWDOWN_LIMIT=0.08, MAX_TRADES=2):
   check_daily_loss(balance,pnl)->bool; check_drawdown(peak,current)->bool;
   check_trade_count(n)->bool; best_day_rule(today,others)->bool (today<=2/3*sum);
   prague_midnight_reset(); is_trading_allowed(account)->tuple[bool,str]
3. MT5PositionSizer: calculate_lots(risk_amount,sl_pips,symbol)->float
4. DrawdownHysteresis: should_resume(last_dd_time,current_dd)->bool

Complete Python file only."""
    code = extract_code(call_openai(p))
    write_src("agent_c_mt5.py", code)


def build_agent_d():
    ctx = doc_section(["regime", "calibration", "entropy", "crowding", "Nash",
                       "M-04", "M-05", "P-01", "F9", "F10", "walk-forward",
                       "partial exit", "resolution window"])
    ctx = ctx[:2000] # type: ignore
    p = f"""Write src/agent_d.py for a trading system.
Doc context: {ctx} # pyre-ignore

Write these 8 classes (complete Python, type-annotated, commented):
1. RegimeClassifier: classify(vix,spy_200ma,breadth,momentum)->str (BULL/BEAR/VOLATILE/CHOPPY/TRENDING)
2. StatisticalSignificanceGate: rate_data(n)->str; confidence_interval(wins,total)->tuple;
   format_stat(wr,n)->str; can_adapt(n)->bool (False if n<50)
3. EdgeCrowdingDetector: detect(pattern,win_rates,avg_rs,slippages,volumes)->str (CLEAR/WARNING/CROWDED)
4. SystemEntropyMonitor: measure(wr_trend,cal_drift,param_age,regime_acc)->str
5. ConditionalExpectancyMatrix: build(history)->dict (only if len>=200)
6. PartialExitRules: get_exits(pattern,entry,r_size)->list[dict]
   BullFlag:+1R->BE,+1.5R->50%,+2R->75%,target->all
   HeadShoulders:+1R->BE,target->100%
   FallingWedge:+1R->BE,+1.5R->50%,+2.5R->all
   OversoldBounce:+0.5R->25%,RSI40->50%,RSI50->all
   SectorSympathy:+1R->50%,+1.5R->all
7. ResolutionWindowCalibrator: get_window(pattern,instrument,history)->int (2x theoretical to start)
8. CalibrationPipeline: weekly_calibration(trades)->dict; monthly_audit(trades)->dict;
   walk_forward_validation(trades)->dict

Complete Python file only."""
    code = extract_code(call_gemini(p))
    write_src("agent_d.py", code)


def build_brain():
    p = """Write src/brain.py - trading system coordinator. Complete Python, async, type-annotated.

from enum import Enum
class TradingState(Enum):
    STANDBY=1; SCANNING=2; ANALYZING=3; POSITIONED=4; EXIT=5

class TradingBrain:
    state=TradingState.STANDBY; positions=[]
    def __init__(self, config): pass  # init agents, Telegram bot
    async def run(self): pass  # main loop during market hours
    async def scan_cycle(self): pass  # call Agent A per instrument
    async def analyze(self, pattern): pass  # call Agent B
    async def execute_trade(self, score, account): pass  # call Agent C
    async def monitor_positions(self): pass  # check belief+exits every 60s
    async def learning_cycle(self, result): pass  # call Agent D after trade
    def record_heartbeat(self): pass  # call every 60s for DMS
    def send_telegram(self, msg): pass  # send iPhone alert
    def emergency_halt(self): pass  # close ALL positions + EMERGENCY alert

Telegram state alerts:
STANDBY->SCANNING: "Scanning markets..."
SCANNING->ANALYZING: "Pattern: {pattern} on {symbol}"
ANALYZING->POSITIONED: "Trade opened: {details}"
POSITIONED->EXIT: "Exiting: {reason}"

Implement all methods fully. Complete Python only."""
    code = extract_code(call_claude("claude-sonnet-4-5", p))
    write_src("brain.py", code)


def build_exit_intelligence():
    p = """Write src/exit_intelligence.py - 7-priority exit system. Complete Python.

from dataclasses import dataclass, field
from enum import Enum

class ExitAction(Enum):
    EXIT="EXIT"; TIGHTEN="TIGHTEN"; CASCADE="CASCADE"; EVALUATE="EVALUATE"; HOLD="HOLD"

@dataclass
class ExitDecision:
    action: ExitAction; priority: int; reason: str; new_stop: float = None

class ExitIntelligence:
    def evaluate(self, position: dict, market: dict, account: dict) -> ExitDecision:
        # P1: price<=stop -> EXIT
        # P2: belief<0.35 -> EXIT "Bayesian: thesis broken"
        # P3: daily_loss>=0.04 -> EXIT "Budget limit"
        # P4: VIX+15% -> TIGHTEN
        # P5: correlated stopped -> CASCADE
        # P6: resolution expired -> EVALUATE
        # P7: -> HOLD
        pass  # implement fully

Complete Python only."""
    code = extract_code(call_claude("claude-sonnet-4-5", p))
    write_src("exit_intelligence.py", code)


def build_dms():
    p = """Write src/dms.py - Dead Man Switch via Telegram. Complete async Python.

import asyncio
from datetime import datetime

class DMSMonitor:
    def __init__(self, bot_token: str, chat_id: str, timeout: int = 300):
        self.last_heartbeat = datetime.now()
        # init telegram bot
    async def run(self): pass  # check every 30s
    def record_heartbeat(self): self.last_heartbeat = datetime.now()
    async def check_timeout(self): pass  # >5min no beat -> alert
    async def send_emergency_alert(self): pass  # "EMERGENCY: offline!"
    async def send_status_ok(self): pass  # hourly ok message

Implement all methods fully. Complete Python only."""
    code = extract_code(call_claude("claude-sonnet-4-5", p))
    write_src("dms.py", code)


def build_data_pipeline():
    p = """Write src/data_pipeline.py - market data feed. Complete async Python.

class DataPipeline:
    INSTRUMENTS = ["SPY","QQQ","IWM","DIA","XLK","XLF","XAUUSD","US100"]
    def __init__(self, finnhub_key: str): pass
    async def fetch_ohlcv(self, symbol: str, tf: str="1d", bars: int=100): pass
    async def fetch_vix(self) -> float: pass
    async def fetch_news(self, symbol: str) -> list: pass
    async def run_continuous(self): pass  # every 60s during market hours
    def is_market_open(self) -> bool: pass  # NYSE 9:30-16:00 ET Mon-Fri
    def store_ohlcv(self, symbol, df, conn): pass  # save to SQLite

Implement all methods using yfinance. Complete Python only."""
    code = extract_code(call_claude("claude-sonnet-4-5", p))
    write_src("data_pipeline.py", code)


def build_main():
    p = """Write src/main.py - single entry point. Complete async Python.

import asyncio, sqlite3, os
from pathlib import Path
from dotenv import load_dotenv # pyre-ignore[21]

class TradingSystem:
    def __init__(self):
        load_dotenv(override=True)
        self.mode = os.getenv("TRADING_MODE","paper")
    async def startup(self):
        # 1. verify paper mode
        # 2. init SQLite from data/schema.sql
        # 3. connect IBKR port 7497
        # 4. connect MT5 if MT5_LOGIN exists
        # 5. start DataPipeline
        # 6. start DMS
        # 7. start TradingBrain
        # 8. telegram: "Trading System V3.0 Online - Paper Mode"
        pass
    async def shutdown(self): pass
    def check_paper(self):
        if self.mode != "paper":
            r = input("Not paper mode! Type YES: ")
            if r != "YES": raise SystemExit("Aborted")

if __name__ == "__main__":
    s = TradingSystem()
    try: asyncio.run(s.startup())
    except KeyboardInterrupt: asyncio.run(s.shutdown())

Implement all methods fully. Complete Python only."""
    code = extract_code(call_claude("claude-sonnet-4-5", p))
    write_src("main.py", code)


def build_tests():
    p = """Write tests/test_integration.py - 10 pytest tests. Complete Python.

Write exactly these functions (each self-contained with its own imports):

def test_kelly_cap():
    from src.agent_c_ibkr import KellySizer
    assert KellySizer().calculate(0.99, 10.0, 100000) <= 4000

def test_f17_belief_cap():
    from src.agent_b import BayesianBeliefTracker
    t = BayesianBeliefTracker(0.5)
    for _ in range(20): t.update("price_toward_large", 0.03)
    assert t.current_belief <= 0.90

def test_belief_drops_adverse():
    from src.agent_b import BayesianBeliefTracker
    t = BayesianBeliefTracker(0.85)
    t.update("price_against_medium", -0.015)
    assert t.current_belief < 0.75

def test_f3_returns_tuple():
    from src.agent_b import CatalystScorer
    r = CatalystScorer().score(70, {"macro":5}, 2.0, None, "orbital", 50)
    assert isinstance(r, tuple) and len(r) == 2

def test_f6_eight_steps():
    from src.agent_c_ibkr import PositionSizingChain
    r = PositionSizingChain().calculate(0.65, 2.0, 10000, "SPY", "margin", 1.5, 0.3, 3, "morning")
    assert "step1" in r and "step8_shares" in r

def test_ftmo_daily_limit():
    from src.agent_c_mt5 import FTMOComplianceLayer
    assert FTMOComplianceLayer.DAILY_LIMIT == 0.04

def test_ftmo_drawdown_limit():
    from src.agent_c_mt5 import FTMOComplianceLayer
    assert FTMOComplianceLayer.DRAWDOWN_LIMIT == 0.08

def test_ftmo_max_trades():
    from src.agent_c_mt5 import FTMOComplianceLayer
    assert FTMOComplianceLayer.MAX_TRADES == 2

def test_budget_freeze():
    from src.agent_a import ContinuousBudgetMonitor
    m = ContinuousBudgetMonitor()
    m.daily_loss_pct = 0.041
    assert m.is_trading_allowed() == False

def test_m04_gate():
    from src.agent_d import StatisticalSignificanceGate
    g = StatisticalSignificanceGate()
    assert g.can_adapt(15) == False
    assert g.can_adapt(250) == True

Complete pytest file only."""
    code = extract_code(call_claude("claude-sonnet-4-5", p))
    write_tests("test_integration.py", code)


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    if not check():
        print("Fix issues above and retry.")
        sys.exit(1)

    start = time.time()

    print("="*62)
    print("  PHASE 1: Direct generation (zero API calls)")
    print("="*62)
    phase1()

    print("="*62)
    print("  PHASE 2: AI code generation")
    print("  Rate limit: 65s pause between each file.")
    print("  Estimated time: ~15 minutes total.")
    print("="*62)

    steps = [
        ("T02 Agent A Patterns (Sonnet)",    build_agent_a),
        ("T03 Agent B Dhatu (Opus)",          build_agent_b),
        ("T04 Agent C IBKR (GPT-4o)",         build_agent_c_ibkr),
        ("T05 Agent C MT5 (GPT-4o)",          build_agent_c_mt5),
        ("T06 Agent D Learning (Gemini)",     build_agent_d),
        ("T07 Brain (Sonnet)",                build_brain),
        ("T08 Exit Intelligence (Sonnet)",    build_exit_intelligence),
        ("T09 DMS (Sonnet)",                  build_dms),
        ("T10 Data Pipeline (Sonnet)",        build_data_pipeline),
        ("T12 Main entry point (Sonnet)",     build_main),
        ("T13 Integration Tests (Sonnet)",    build_tests),
    ]

    for name, fn in steps:
        print(f"\n  --- {name} ---")
        try:
            fn()
        except Exception as e:
            print(f"  ERROR in {name}: {e}")
            (SRC_DIR / f"ERROR_{name.replace(' ','_')}.txt").write_text(str(e))
            print("  Continuing to next file...")
        pace(65)

    elapsed = int(time.time() - start)
    print("\n" + "="*62)
    print(f"  BUILD COMPLETE ({elapsed // 60}m {elapsed % 60}s)")
    print("="*62)
    files = sorted(SRC_DIR.glob("*.py"))
    print(f"\n  {len(files)} files in src/:")
    for f in files:
        lines = len(f.read_text(encoding="utf-8").split("\n"))
        print(f"    {f.name:35s} ({lines} lines)")
    print(f"\n  Run: python src/main.py")
    print("="*62)
