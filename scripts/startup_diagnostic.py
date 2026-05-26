"""
Sovereign Startup Diagnostic
Tests every critical path independently before risking capital.
Run this BEFORE starting the live system.
"""

import asyncio
import os
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

LOG_PATH = Path("logs/startup_diagnostic.log")
LOG_PATH.parent.mkdir(exist_ok=True)

results = []


def log(msg: str, level: str = "INFO"):
    ts = datetime.now(timezone.utc).isoformat()
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def ok(msg: str):
    results.append(("OK", msg))
    log(f"  OK  {msg}")


def warn(msg: str):
    results.append(("WARN", msg))
    log(f"  WARN  {msg}", "WARN")


def fail(msg: str):
    results.append(("FAIL", msg))
    log(f"  FAIL  {msg}", "ERROR")


# ═══════════════════════════════════════════════════════════════
# 1. SAFETY & MODE CHECK
# ═══════════════════════════════════════════════════════════════
def check_safety():
    log("\n" + "=" * 60)
    log("PHASE 1: SAFETY & MODE CHECK")
    log("=" * 60)

    try:
        from vault import Vault
        mode = Vault.get("TRADING_MODE", "paper")
        forced = Vault.get("FORCED_PAPER_MODE", "0") == "1"
        allow_live = Vault.get("ALLOW_FORCE_LIVE", "0") == "1"

        log(f"TRADING_MODE from Vault: {mode}")
        log(f"FORCED_PAPER_MODE: {forced}")
        log(f"ALLOW_FORCE_LIVE: {allow_live}")

        if forced:
            ok("FORCED_PAPER_MODE is ON — system is safe")
        elif mode == "paper":
            ok("TRADING_MODE is 'paper' — no real money at risk")
        elif mode == "ibkr_paper":
            ok("TRADING_MODE is 'ibkr_paper' — paper account only")
        elif mode == "live" and not allow_live:
            fail("TRADING_MODE is 'live' but ALLOW_FORCE_LIVE is OFF — safety will block this")
        elif mode == "live" and allow_live:
            warn("TRADING_MODE is 'live' AND ALLOW_FORCE_LIVE is ON — REAL MONEY AT RISK")
        else:
            warn(f"Unknown TRADING_MODE: {mode}")

    except Exception as e:
        fail(f"Safety check failed: {e}")


# ═══════════════════════════════════════════════════════════════
# 2. FILE SYSTEM & PERMISSIONS
# ═══════════════════════════════════════════════════════════════
def check_filesystem():
    log("\n" + "=" * 60)
    log("PHASE 2: FILE SYSTEM & PERMISSIONS")
    log("=" * 60)

    dirs = ["data", "logs", "models", "src"]
    for d in dirs:
        p = Path(d)
        if p.exists() and p.is_dir():
            ok(f"Directory '{d}' exists")
        else:
            fail(f"Directory '{d}' missing")

    # Write test
    try:
        test_file = Path("data/.diagnostic_write_test")
        test_file.write_text("test")
        test_file.unlink()
        ok("Project path is writable")
    except Exception as e:
        fail(f"Project path NOT writable: {e}")

    # Database
    db_path = Path("data/trading.db")
    if db_path.exists():
        ok(f"Database exists ({db_path.stat().st_size / 1024:.1f} KB)")
    else:
        warn("Database does not exist yet (will be created on first run)")

    schema_path = Path("data/schema.sql")
    if schema_path.exists():
        ok("Schema file exists")
    else:
        warn("Schema file missing (basic tables will be auto-created)")


# ═══════════════════════════════════════════════════════════════
# 3. PYTHON ENVIRONMENT
# ═══════════════════════════════════════════════════════════════
def check_python_env():
    log("\n" + "=" * 60)
    log("PHASE 3: PYTHON ENVIRONMENT")
    log("=" * 60)

    log(f"Python version: {sys.version}")
    log(f"Platform: {sys.platform}")

    critical_packages = [
        ("ib_insync", "IBKR connectivity"),
        ("aiohttp", "Async HTTP"),
        ("polars", "DataFrame engine"),
        ("numpy", "Math kernels"),
        ("pandas", "Data analysis"),
        ("httpx", "HTTP client"),
    ]

    for pkg, purpose in critical_packages:
        try:
            __import__(pkg)
            ok(f"{pkg} installed ({purpose})")
        except ImportError:
            warn(f"{pkg} NOT installed ({purpose}) — some features will be disabled")

    # Check optional packages
    optional = [
        ("zstandard", "Compression"),
        ("winloop", "Event loop (Windows)"),
        ("keyring", "Credential vault"),
        ("fastembed", "Embedding engine"),
    ]
    for pkg, purpose in optional:
        try:
            __import__(pkg)
            ok(f"{pkg} installed ({purpose})")
        except ImportError:
            warn(f"{pkg} NOT installed ({purpose})")


# ═══════════════════════════════════════════════════════════════
# 4. VAULT & SECRETS
# ═══════════════════════════════════════════════════════════════
def check_vault():
    log("\n" + "=" * 60)
    log("PHASE 4: VAULT & SECRETS")
    log("=" * 60)

    try:
        from vault import Vault

        keys_to_check = [
            ("TELEGRAM_BOT_TOKEN", "Telegram alerts"),
            ("TELEGRAM_CHAT_ID", "Telegram target"),
            ("IBKR_HOST", "IBKR host"),
            ("IBKR_PORT", "IBKR port"),
            ("IBKR_CLIENT_ID", "IBKR client ID"),
            ("MT5_LOGIN", "MT5 login"),
            ("MT5_SERVER", "MT5 server"),
            ("GOOGLE_API_KEY", "Dhatu/Google"),
            ("ANTHROPIC_API_KEY", "Dhatu/Claude"),
            ("OPENBB_PAT", "OpenBB data"),
            ("FINNHUB_API_KEY", "Finnhub data"),
            ("QUESTDB_ENABLED", "QuestDB toggle"),
        ]

        for key, purpose in keys_to_check:
            val = Vault.get(key)
            if val and str(val).strip() and "YOUR_" not in str(val).upper():
                ok(f"{key} configured ({purpose})")
            else:
                warn(f"{key} missing or placeholder ({purpose})")

    except Exception as e:
        fail(f"Vault check failed: {e}")


# ═══════════════════════════════════════════════════════════════
# 5. COMPONENT IMPORTS
# ═══════════════════════════════════════════════════════════════
def check_component_imports():
    log("\n" + "=" * 60)
    log("PHASE 5: COMPONENT IMPORTS")
    log("=" * 60)

    components = [
        ("brain", "TradingBrain"),
        ("data_pipeline", "DataPipeline"),
        ("dhatu_oracle", "DhatuOracle"),
        ("dms", "DMSMonitor"),
        ("intelligence_bus", "SharedIntelligenceBus"),
        ("questdb_adapter", "QuestDBAdapter"),
        ("api_server", "APIServer"),
        ("native_slm", "NativeSLM"),
    ]

    for module_name, class_name in components:
        try:
            module = __import__(module_name)
            cls = getattr(module, class_name, None)
            if cls:
                ok(f"{module_name}.{class_name} importable")
            else:
                warn(f"{module_name}.{class_name} not found in module")
        except ImportError as e:
            warn(f"{module_name} import failed: {e}")
        except Exception as e:
            fail(f"{module_name} unexpected error: {e}")


# ═══════════════════════════════════════════════════════════════
# 6. DATABASE SCHEMA
# ═══════════════════════════════════════════════════════════════
def check_database():
    log("\n" + "=" * 60)
    log("PHASE 6: DATABASE SCHEMA")
    log("=" * 60)

    db_path = Path("data/trading.db")
    if not db_path.exists():
        warn("No database to check")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        critical_tables = ["positions", "trades", "orders", "ledger"]
        for t in critical_tables:
            if t in tables:
                ok(f"Table '{t}' exists")
            else:
                warn(f"Table '{t}' missing")

        if "agent_d_trades" in tables:
            ok("Table 'agent_d_trades' exists (Agent D learning data)")
        else:
            warn("Table 'agent_d_trades' missing (Agent D will create on first trade)")

    except Exception as e:
        fail(f"Database check failed: {e}")


# ═══════════════════════════════════════════════════════════════
# 7. PATTERN DETECTION SMOKE TEST
# ═══════════════════════════════════════════════════════════════
def check_pattern_detection():
    log("\n" + "=" * 60)
    log("PHASE 7: PATTERN DETECTION SMOKE TEST")
    log("=" * 60)

    try:
        import polars as pl

        from agent_a import PatternRecognizer

        recognizer = PatternRecognizer()

        # Generate synthetic bullish data for bull flag
        data = {
            "open": [100.0 + i * 0.01 for i in range(30)],
            "high": [100.0 + i * 0.01 + 0.05 for i in range(30)],
            "low": [100.0 + i * 0.01 - 0.05 for i in range(30)],
            "close": [100.0 + i * 0.01 for i in range(30)],
            "volume": [1000000] * 30,
        }
        # Make a clear pole: +5% in 10 bars
        for i in range(10, 20):
            data["close"][i] = data["close"][i - 1] * 1.005
            data["high"][i] = data["close"][i] + 0.05
            data["low"][i] = data["close"][i] - 0.05
        # Make a tight flag
        for i in range(20, 30):
            data["close"][i] = data["close"][19] + (i - 20) * 0.01
            data["high"][i] = data["close"][19] + 0.15
            data["low"][i] = data["close"][19] - 0.15

        df = pl.DataFrame(data)

        result = recognizer.detect_bull_flag(df)
        if result:
            ok(f"Bull flag detected on synthetic data (confidence={result.confidence}%)")
            log(f"    Entry={result.entry:.2f}, Stop={result.stop:.2f}, Target={result.target:.2f}, R:R={result.r_r_ratio:.2f}")
        else:
            warn("Bull flag NOT detected on synthetic data (threshold may be too strict)")

        # Test RSI oversold
        rsi_data = {
            "open": [100.0] * 30,
            "high": [100.5] * 30,
            "low": [99.5] * 30,
            "close": [100.0 - i * 0.3 for i in range(30)],
            "volume": [1000000] * 30,
            "rsi": [70 - i * 2 for i in range(30)],  # RSI drops from 70 to 10
        }
        df_rsi = pl.DataFrame(rsi_data)
        result2 = recognizer.detect_oversold_bounce(df_rsi)
        if result2:
            ok(f"Oversold bounce detected (RSI-based, confidence={result2.confidence}%)")
        else:
            warn("Oversold bounce NOT detected on synthetic data")

    except Exception as e:
        fail(f"Pattern detection smoke test failed: {e}")


# ═══════════════════════════════════════════════════════════════
# 8. ASYNC HEALTH CHECK
# ═══════════════════════════════════════════════════════════════
async def check_async_components():
    log("\n" + "=" * 60)
    log("PHASE 8: ASYNC COMPONENT HEALTH")
    log("=" * 60)

    # Intelligence Bus
    try:
        from intelligence_bus import get_bus
        bus = get_bus()
        ok("IntelligenceBus created")
        stats = bus.get_stats()
        log(f"    Bus stats: {stats}")
    except Exception as e:
        fail(f"IntelligenceBus failed: {e}")

    # QuestDB (if enabled)
    try:
        from questdb_adapter import QuestDBAdapter
        from vault import Vault

        qdb_enabled = Vault.get("QUESTDB_ENABLED", "true").lower() == "true"
        if qdb_enabled:
            qdb = QuestDBAdapter(
                host=Vault.get("QUESTDB_HOST", "localhost"),
                ilp_port=int(Vault.get("QUESTDB_PORT", "9009")),
                pg_port=int(Vault.get("QUESTDB_PG_PORT", "8812")),
                enabled=True,
                connect_timeout_sec=5.0,
            )
            await qdb.start()
            if qdb.enabled:
                ok("QuestDB connected")
            else:
                warn("QuestDB offline (non-critical, system will use SQLite fallback)")
        else:
            warn("QuestDB disabled in config")
    except Exception as e:
        warn(f"QuestDB check failed (non-critical): {e}")

    # Native SLM
    try:
        from native_slm import NativeSLM
        slm = NativeSLM()
        if slm.is_available:
            ok("Native SLM is available")
        else:
            warn("Native SLM offline (trading continues with math-only execution)")
    except Exception as e:
        warn(f"Native SLM check failed: {e}")

    # Dhatu Oracle
    try:
        from vault import Vault
        if Vault.get("GOOGLE_API_KEY") or Vault.get("ANTHROPIC_API_KEY"):
            from dhatu_oracle import DhatuOracle
            oracle = DhatuOracle(
                google_api_key=Vault.get("GOOGLE_API_KEY", ""),
                anthropic_api_key=Vault.get("ANTHROPIC_API_KEY", ""),
            )
            ok("DhatuOracle instantiated (API keys present)")
        else:
            warn("DhatuOracle skipped (no API keys)")
    except Exception as e:
        warn(f"DhatuOracle check failed: {e}")


# ═══════════════════════════════════════════════════════════════
# SUMMARY
# ═══════════════════════════════════════════════════════════════
def print_summary():
    log("\n" + "=" * 60)
    log("DIAGNOSTIC SUMMARY")
    log("=" * 60)

    ok_count = sum(1 for r in results if r[0] == "OK")
    warn_count = sum(1 for r in results if r[0] == "WARN")
    fail_count = sum(1 for r in results if r[0] == "FAIL")

    log(f"Results: {ok_count} OK, {warn_count} WARN, {fail_count} FAIL")

    if fail_count == 0 and warn_count == 0:
        log("\n ALL SYSTEMS GO. Ready for startup.")
    elif fail_count == 0:
        log("\n SYSTEM FUNCTIONAL with warnings. Review WARN items before live trading.")
    else:
        log("\n DO NOT START. Fix FAIL items first.")

    log(f"\nFull log written to: {LOG_PATH}")


async def main():
    log("=" * 60)
    log("SOVEREIGN STARTUP DIAGNOSTIC")
    log(f"Started at: {datetime.now(timezone.utc).isoformat()}")
    log("=" * 60)

    check_safety()
    check_filesystem()
    check_python_env()
    check_vault()
    check_component_imports()
    check_database()
    check_pattern_detection()
    await check_async_components()
    print_summary()


if __name__ == "__main__":
    asyncio.run(main())
