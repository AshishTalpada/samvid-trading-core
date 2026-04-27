# pyre-ignore-all-errors
"""
╔══════════════════════════════════════════════════════════════════════╗
║  TRADING SYSTEM V3.0 — WINDOWS SETUP SCRIPT                         ║
║  Run this FIRST on your Windows 11 machine                           ║
║                                                                      ║
║  Fixes automatically:                                                ║
║    ✓ Python version check (needs 3.10–3.12, you have 3.14.3)        ║
║    ✓ Creates correct project folder (NOT system32)                   ║
║    ✓ Sets up virtual environment                                     ║
║    ✓ Installs all packages                                           ║
║    ✓ Creates folder structure                                        ║
║    ✓ Verifies everything works                                       ║
║                                                                      ║
║  Usage:  python setup_windows.py                                     ║
║  Run as: Normal user (NOT administrator)                             ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import subprocess
import platform
from pathlib import Path

# ── COLOURS FOR WINDOWS TERMINAL ─────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def err(msg):  print(f"  {RED}✗{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}⚠{RESET} {msg}")
def info(msg): print(f"  {CYAN}→{RESET} {msg}")
def head(msg): print(f"\n{BOLD}{msg}{RESET}\n{'─'*60}")


# ── STEP 1: CHECK PYTHON VERSION ──────────────────────────────────────

head("STEP 1: Python Version Check")

major = sys.version_info.major
minor = sys.version_info.minor
patch = sys.version_info.micro
current = f"{major}.{minor}.{patch}"

print(f"  You have: Python {current}")
print(f"  You need: Python 3.10, 3.11, or 3.12")

if major == 3 and 10 <= minor <= 12:
    ok(f"Python {current} is compatible!")
else:
    err(f"Python {current} is NOT compatible with this system.")
    print(f"""
  {RED}PYTHON VERSION INCOMPATIBLE — FIX REQUIRED{RESET}
  ─────────────────────────────────────────────
  You have Python 3.14.3. CrewAI and several trading packages
  require Python 3.10, 3.11, or 3.12.

  HOW TO FIX (Windows 11):
  ─────────────────────────
  Option A — Use pyenv-win (recommended):
    1. Open PowerShell as Administrator
    2. Run:
       winget install pyenv-win.pyenv-win
    3. Close and reopen PowerShell (normal user)
    4. Run:
       pyenv install 3.11.9
       pyenv global 3.11.9
    5. Verify: python --version  →  should say 3.11.9
    6. Re-run this script: python setup_windows.py

  Option B — Install Python 3.11 directly:
    1. Go to: https://www.python.org/downloads/release/python-3119/
    2. Download: "Windows installer (64-bit)"
    3. During install: CHECK "Add python.exe to PATH"
    4. After install: python --version  →  3.11.9
    5. Re-run: python setup_windows.py

  {YELLOW}Do NOT delete Python 3.14 — just install 3.11 alongside it.{RESET}
  {YELLOW}Windows lets you have multiple Python versions.{RESET}
""")
    input("  Press Enter to exit...")
    sys.exit(1)


# ── STEP 2: CHECK PROJECT PATH ────────────────────────────────────────

head("STEP 2: Project Folder Check")

FORBIDDEN_PATHS = [
    "C:\\WINDOWS",
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
    "C:\\Users\\Public",
]

RECOMMENDED_PATH = Path("C:\\TradingSystem")
current_path = Path.cwd()

print(f"  Current location: {current_path}")

in_forbidden = any(str(current_path).startswith(fp) for fp in FORBIDDEN_PATHS)

if in_forbidden:
    warn(f"You are in a system folder: {current_path}")
    warn("This is dangerous — Windows restricts writing here.")
    print(f"""
  {RED}WRONG LOCATION — MOVE YOUR PROJECT{RESET}
  ─────────────────────────────────────────
  Your project path is set to {current_path}

  This is a Windows system directory. Your trading system
  cannot run here safely. Let me move it for you.

  Creating correct project folder: {RECOMMENDED_PATH}
""")
    try:
        RECOMMENDED_PATH.mkdir(parents=True, exist_ok=True)
        ok(f"Created: {RECOMMENDED_PATH}")
        print(f"""
  {YELLOW}IMPORTANT: Open a new terminal and navigate there:{RESET}
  cd C:\\TradingSystem

  Then copy all your files there:
  xcopy /E /I . C:\\TradingSystem

  Then re-run: python setup_windows.py
""")
        input("  Press Enter to exit...")
        sys.exit(0)
    except PermissionError:
        err("Cannot create folder. Run this script as normal user (not Admin).")
        sys.exit(1)
else:
    ok(f"Project location looks good: {current_path}")


# ── STEP 3: CREATE FOLDER STRUCTURE ──────────────────────────────────

head("STEP 3: Creating Folder Structure")

folders = ["src", "tests", "outputs", "logs", "data", ".cursor"]
for folder in folders:
    Path(folder).mkdir(exist_ok=True)
    ok(f"Folder: {folder}/")


# ── STEP 4: CREATE VIRTUAL ENVIRONMENT ───────────────────────────────

head("STEP 4: Virtual Environment")

venv_path = Path("venv")
if venv_path.exists():
    ok("Virtual environment already exists")
else:
    info("Creating virtual environment...")
    result = subprocess.run(
        [sys.executable, "-m", "venv", "venv"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        ok("Virtual environment created: venv/")
    else:
        err(f"Failed to create venv: {result.stderr}")
        sys.exit(1)

# Check if venv is active
in_venv = hasattr(sys, 'real_prefix') or (
    hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix
)

if not in_venv:
    print(f"""
  {YELLOW}⚠ Virtual environment not activated{RESET}
  ─────────────────────────────────────────
  Run these commands, then re-run this script:

    {CYAN}venv\\Scripts\\activate{RESET}
    {CYAN}python setup_windows.py{RESET}

  You will see (venv) at the start of your command line when active.
""")
    input("  Press Enter to exit...")
    sys.exit(0)
else:
    ok("Virtual environment is active")


# ── STEP 5: INSTALL PACKAGES ─────────────────────────────────────────

head("STEP 5: Installing Packages")

# Core packages in install order
packages = [
    # Core first
    ("pip", "pip install --upgrade pip", "Upgrade pip"),
    ("python-dotenv", "pip install python-dotenv", "Load .env files"),
    ("pydantic", "pip install pydantic>=2.8.0", "Data validation"),
    ("rich", "pip install rich", "Beautiful terminal output"),
    ("psutil", "pip install psutil", "System monitoring"),

    # AI providers
    ("anthropic", "pip install anthropic>=0.49.0", "Claude Opus/Sonnet 4.6"),
    ("openai", "pip install openai>=1.68.0", "GPT-5.4 Thinking"),
    ("google-generativeai", "pip install google-generativeai>=0.9.0", "Gemini 3.1 Pro"),

    # LangChain
    ("langchain", "pip install langchain>=0.3.0", "LangChain core"),
    ("langchain-anthropic", "pip install langchain-anthropic>=0.3.0", "Claude wrapper"),
    ("langchain-openai", "pip install langchain-openai>=0.3.0", "GPT wrapper"),
    ("langchain-google-genai", "pip install langchain-google-genai>=2.1.0", "Gemini wrapper"),

    # CrewAI
    ("crewai", "pip install crewai>=0.80.0", "Multi-AI orchestration"),
    ("crewai-tools", "pip install crewai-tools>=0.14.0", "CrewAI tools"),

    # Market data
    ("yfinance", "pip install yfinance>=0.2.54", "Historical market data"),
    ("pandas", "pip install pandas>=2.2.0", "Data handling"),
    ("numpy", "pip install numpy>=1.26.0", "Math"),
    ("scipy", "pip install scipy>=1.13.0", "Statistics"),
    ("scikit-learn", "pip install scikit-learn>=1.5.0", "Regime classification"),
    ("pandas-ta", "pip install pandas-ta>=0.3.14b0", "Technical indicators"),
    ("finnhub-python", "pip install finnhub-python>=2.4.20", "News + market feed"),

    # Brokers
    ("ib_insync", "pip install ib_insync>=0.9.86", "IBKR TWS API"),
    # MetaTrader5 installed separately below (Windows only)

    # Infrastructure
    ("aiohttp", "pip install aiohttp>=3.10.0", "Async HTTP"),
    ("websockets", "pip install websockets>=13.0", "WebSocket feeds"),
    ("python-telegram-bot", "pip install python-telegram-bot>=21.0", "Telegram alerts"),
    ("structlog", "pip install structlog>=24.4.0", "Structured logging"),
    ("tenacity", "pip install tenacity>=9.0.0", "Retry logic"),
    ("schedule", "pip install schedule>=1.2.2", "Weekly calibration"),
    ("pytz", "pip install pytz>=2024.1", "Prague midnight FTMO reset"),

    # Testing
    ("pytest", "pip install pytest pytest-asyncio pytest-cov", "Testing framework"),
]

failed = []
for pkg_name, cmd, description in packages:
    print(f"  Installing {description}...", end=" ", flush=True)
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"{GREEN}✓{RESET}")
    else:
        print(f"{RED}✗{RESET}")
        failed.append((pkg_name, result.stderr[:200])) # type: ignore

# MetaTrader5 separately (Windows only)
print(f"  Installing MetaTrader5 (Windows only)...", end=" ", flush=True)
result = subprocess.run(
    "pip install MetaTrader5>=5.0.4522",
    shell=True, capture_output=True, text=True
)
if result.returncode == 0:
    print(f"{GREEN}✓{RESET}")
else:
    print(f"{YELLOW}○ (install after FTMO account is open){RESET}")

if failed:
    print(f"\n  {YELLOW}Some packages failed:{RESET}")
    for pkg, error in failed:
        err_str = error[:100] # type: ignore
        print(f"    {RED}✗{RESET} {pkg}: {err_str}")
    print(f"\n  Try manually: pip install <package>")
else:
    ok("All packages installed successfully")


# ── STEP 6: VERIFY CRITICAL IMPORTS ──────────────────────────────────

head("STEP 6: Verifying Critical Imports")

checks = [
    ("crewai", "CrewAI orchestration"),
    ("anthropic", "Claude API"),
    ("openai", "GPT API"),
    ("google.generativeai", "Gemini API"),
    ("langchain_anthropic", "LangChain Claude"),
    ("langchain_openai", "LangChain GPT"),
    ("ib_insync", "IBKR connection"),
    ("yfinance", "Market data"),
    ("pandas", "Data handling"),
    ("scipy", "Statistics"),
    ("telegram", "Telegram alerts"),
    ("sqlite3", "Database (built-in)"),
]

all_ok = True
for module, description in checks:
    try:
        __import__(module) # pyre-ignore[21]
        ok(f"{description} ({module})")
    except ImportError:
        err(f"{description} ({module}) — not installed")
        all_ok = False


# ── STEP 7: CREATE .env FROM TEMPLATE ────────────────────────────────

head("STEP 7: Environment File")

env_path = Path(".env")
env_example = Path(".env.example")

if env_path.exists():
    ok(".env already exists — not overwriting")
elif env_example.exists():
    import shutil
    shutil.copy(env_example, env_path)
    ok(".env created from .env.example")
    warn("Edit .env now and add your API keys before continuing")
else:
    # Create minimal .env
    env_content = """# Trading System V3.0 — API Keys
# Fill in your real values below

ANTHROPIC_API_KEY=sk-ant-your-key-here
OPENAI_API_KEY=sk-your-key-here
GOOGLE_API_KEY=your-google-key-here
FINNHUB_API_KEY=your-finnhub-key-here

TELEGRAM_BOT_TOKEN=your-bot-token-here
TELEGRAM_CHAT_ID=your-chat-id-here

IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1

MT5_LOGIN=your-mt5-login
MT5_PASSWORD=your-mt5-password
MT5_SERVER=your-ftmo-server

TRADING_MODE=paper
STARTING_CAPITAL_CAD=500
IBKR_ALLOCATION_CAD=255
FTMO_ALLOCATION_CAD=245
FTMO_ACCOUNT_SIZE=25000
RISK_PER_TRADE=1.0
F16_DECISION=B
"""
    env_path.write_text(env_content)
    ok(".env created — fill in your API keys now")


# ── STEP 8: SQLITE TEST ───────────────────────────────────────────────

head("STEP 8: Database Check")
import sqlite3
ok(f"SQLite {sqlite3.sqlite_version} — ready")

# Quick test
conn = sqlite3.connect(":memory:")
conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
conn.execute("INSERT INTO test VALUES (1, 'working')")
result = conn.execute("SELECT value FROM test").fetchone()
conn.close()
if result and result[0] == "working":
    ok("SQLite read/write test passed")


# ── FINAL SUMMARY ─────────────────────────────────────────────────────

head("SETUP COMPLETE")

if all_ok:
    print(f"""
  {GREEN}✓ Everything ready. Next steps:{RESET}

  1. Add your API keys to .env
     {CYAN}notepad .env{RESET}

  2. Create your Telegram bot:
     - Message @BotFather on Telegram
     - Type /newbot → follow instructions
     - Copy the token to .env as TELEGRAM_BOT_TOKEN

  3. Place your documentation in this folder:
     {CYAN}EVERYTHING_FINAL.md{RESET}
     {CYAN}UNIFIED_V3_WITH_SIMULATION.md{RESET}

  4. Open FTMO free trial:
     {CYAN}https://ftmo.com{RESET} → Free Trial → $25,000 Swing Account

  5. Install MT5 when FTMO trial opens:
     Download from FTMO's platform page

  6. Fund IBKR account:
     Transfer $255 CAD to your IBKR account

  7. Run the orchestrator:
     {CYAN}python orchestrator.py{RESET}

  {YELLOW}⚠ Important reminders:{RESET}
  - No UPS: your trading is at risk during power cuts
    → Get a basic UPS before going live (~$50 CAD)
  - DMS on iPhone: Telegram bot will send emergency alerts
  - IBKR is regular margin (not RRSP): keep tax records
  - No trusted person: please tell someone about this project
""")
else:
    warn("Some packages failed. Fix errors above, then re-run.")
    print(f"  {CYAN}python setup_windows.py{RESET}")

input("\n  Press Enter to close...")
