"""
SETO V22.6 — Memory Leak Diagnostic (File-output version)
Writes directly to a log file to avoid stdout buffering issues.
"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))
# Force unbuffered output
os.environ["PYTHONUNBUFFERED"] = "1"

import asyncio
import gc
import tracemalloc
import psutil
import time as _time

proc = psutil.Process()
LOG_FILE = os.path.join(os.path.dirname(__file__), "memory_report.txt")

def mb(b): return f"{b / (1024*1024):.1f}"

def log(msg):
    info = proc.memory_info()
    line = f"[{_time.strftime('%H:%M:%S')}] RSS={mb(info.rss):>8} MB | VMS={mb(info.vms):>8} MB | {msg}"
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")
    print(line, flush=True)

async def run_diagnostic():
    # Clear old report
    with open(LOG_FILE, "w") as f:
        f.write("=== SOVEREIGN MEMORY DIAGNOSTIC ===\n")
    
    tracemalloc.start(10)
    log("BASELINE — before any project imports")

    # Phase 1: Track import weight
    log("--- PHASE 1: IMPORT COSTS ---")
    
    import numpy; log("After import numpy")
    import pandas; log("After import pandas")
    import polars; log("After import polars")
    import aiohttp; log("After import aiohttp")
    
    try:
        import chromadb; log("After import chromadb")
    except: log("chromadb not available")
    
    try:
        import yfinance; log("After import yfinance")
    except: log("yfinance not available")
    
    import importlib
    try:
        fastembed = importlib.import_module("fastembed")
        TextEmbedding = fastembed.TextEmbedding
        log("After import fastembed.TextEmbedding")
    except: log("fastembed not available (OK)")

    try:
        import ib_insync; log("After import ib_insync")
    except: log("ib_insync not available")

    try:
        openbb = importlib.import_module("openbb")
        log("After import openbb (HEAVY)")
    except: log("openbb not available")

    gc.collect()
    log("After gc.collect()")

    # Phase 2: System import
    log("--- PHASE 2: SYSTEM INIT ---")
    from main import TradingSystem
    log("After 'from main import TradingSystem' (loads brain.py + all agents)")
    
    gc.collect()
    log("After gc.collect()")
    
    s = TradingSystem()
    log("After TradingSystem()")
    
    await s.async_init()
    log("After async_init()")
    gc.collect()
    log("After gc.collect()")

    # Phase 3: Startup with per-second tracking
    log("--- PHASE 3: STARTUP (60s tracking) ---")
    snap1 = tracemalloc.take_snapshot()
    
    startup_task = asyncio.create_task(s.startup())
    
    for i in range(60):
        await asyncio.sleep(1)
        extra = ""
        if i in (15, 30, 45):
            gc.collect()
            extra = " [gc.collect()]"
        log(f"T+{i+1:02d}s{extra}")
        
        if i == 29:
            snap2 = tracemalloc.take_snapshot()
            diff = snap2.compare_to(snap1, 'lineno')
            with open(LOG_FILE, "a") as f:
                f.write("\n--- TOP 20 MEMORY GROWTH (first 30s) ---\n")
                for stat in diff[:20]:
                    f.write(f"  {stat}\n")
                f.write("\n--- TOP 10 BY FILE ---\n")
                for stat in snap2.compare_to(snap1, 'filename')[:10]:
                    f.write(f"  {stat}\n")
                f.write("--- END ---\n\n")
            log("Snapshot written to report file")
    
    # Final snapshot
    snap3 = tracemalloc.take_snapshot()
    diff2 = snap3.compare_to(snap1, 'lineno')
    with open(LOG_FILE, "a") as f:
        f.write("\n--- TOP 20 MEMORY GROWTH (full 60s) ---\n")
        for stat in diff2[:20]:
            f.write(f"  {stat}\n")
        f.write("\n--- TOP 10 BY FILE ---\n")
        for stat in snap3.compare_to(snap1, 'filename')[:10]:
            f.write(f"  {stat}\n")

    log("--- SHUTTING DOWN ---")
    startup_task.cancel()
    try: await startup_task
    except: pass
    try: await s.shutdown()
    except: pass
    log("DONE")

if __name__ == "__main__":
    import signal
    signal.signal(signal.SIGINT, signal.default_int_handler)
    try:
        asyncio.run(run_diagnostic())
    except KeyboardInterrupt:
        print("\n[DIAGNOSTIC] Terminated by user", flush=True)
    except Exception as e:
        print(f"\n[DIAGNOSTIC] Fatal: {e}", flush=True)
        import traceback; traceback.print_exc()
