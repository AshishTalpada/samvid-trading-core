import sqlite3
import time
import logging
from datetime import datetime, timezone
import os
import sys

# Setup minimal logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - WATCHDOG - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "data/trading.db"
CHECK_INTERVAL = 30          # Check every 30 seconds (tightened from 60)
LIVENESS_TIMEOUT = 120       # Task is live-locked if heartbeat > 120s stale
SILENCE_TIMEOUT = 60         # System crashed if > 60s total silence (matches DMS)
MEMORY_THRESHOLD_MB = 1200   # GAP-75: Restart if RAM > 1.2GB to purge leaks (Fallback)

def get_dynamic_memory_threshold() -> float:
    """Calculates a safe memory threshold based on total system RAM (70% or max 2GB)."""
    try:
        import psutil
        total_gb = psutil.virtual_memory().total / (1024**3)
        # We aim for 70% of system RAM but cap at 2.5GB for this specific engine architecture
        threshold = min(total_gb * 0.7 * 1024, 2500.0) 
        return max(1200.0, threshold)
    except Exception:
        return 1200.0

# Shared task heartbeat registry — main process writes here; watchdog reads it
TASK_HEARTBEAT_FILE = "data/task_heartbeats.json"


def check_heartbeat() -> bool:
    """Returns True if the system is alive, False if silent/crashed."""
    if not os.path.exists(DB_PATH):
        logger.warning(f"Database {DB_PATH} not found. Waiting...")
        return True

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM system_state WHERE key='last_heartbeat'")
        row = cursor.fetchone()
        conn.close()

        if row:
            last_hb_str = row[0]
            last_hb = datetime.fromisoformat(last_hb_str)
            seconds_since = (datetime.now(timezone.utc) - last_hb).total_seconds()

            if seconds_since > SILENCE_TIMEOUT:
                logger.critical(
                    f"SYSTEM SILENCE DETECTED! Last heartbeat was {seconds_since:.1f}s ago "
                    f"(threshold: {SILENCE_TIMEOUT}s). System may have crashed or live-locked."
                )
                return False
            else:
                logger.info(f"System Pulse: OK ({seconds_since:.1f}s since last heartbeat)")
                return True
        else:
            logger.warning("No heartbeat record found in database.")
            return True
    except Exception as e:
        logger.error(f"Watchdog Error during check: {e}")
        return True


def check_task_liveness() -> dict:
    """
    Fix 14: Detects live-locked tasks by reading per-task heartbeat timestamps.
    A task is considered live-locked if it hasn't written a heartbeat in LIVENESS_TIMEOUT seconds.
    """
    import json
    stale_tasks = {}
    if not os.path.exists(TASK_HEARTBEAT_FILE):
        return stale_tasks
    try:
        with open(TASK_HEARTBEAT_FILE, "r") as f:
            heartbeats = json.load(f)
        now = time.time()
        for task_name, last_ts in heartbeats.items():
            age = now - float(last_ts)
            if age > LIVENESS_TIMEOUT:
                stale_tasks[task_name] = age
                logger.critical(
                    f"LIVE-LOCK DETECTED: Task '{task_name}' has not pulsed in {age:.0f}s "
                    f"(threshold: {LIVENESS_TIMEOUT}s). Task may be stuck in an infinite await."
                )
    except Exception as e:
        logger.error(f"Watchdog: Task liveness check failed: {e}")
    return stale_tasks


def check_memory_usage() -> float:
    try:
        import psutil
        # GAP-93 FIX: Ghost PID detection
        # If the main.pid file is missing, we attempt to find the process by name
        pid_file = "data/main.pid"
        target_pid = None
        
        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    target_pid = int(f.read().strip())
            except Exception: pass

        if not target_pid or not psutil.pid_exists(target_pid):
            # Fallback: Find by process name if file is missing/stale
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                if "python" in (proc.info['name'] or "").lower():
                    cmdline = proc.info['cmdline'] or []
                    if any("src/main.py" in arg for arg in cmdline):
                        target_pid = proc.info['pid']
                        logger.info(f"Watchdog: Ghost PID {target_pid} discovered via process scan (GAP-93).")
                        break
        
        if target_pid and psutil.pid_exists(target_pid):
            target_process = psutil.Process(target_pid)
            return target_process.memory_info().rss / (1024 * 1024)
            
        return 0.0
    except Exception as e:
        logger.error(f"Watchdog: Memory check failed: {e}")
        return 0.0


from typing import Set # pyre-ignore[21]
restart_history: Set[float] = set()

def _write_watchdog_pid() -> None:
    """Record Watchdog PID for the main engine to verify connectivity."""
    try:
        pid = os.getpid()
        os.makedirs("data", exist_ok=True)
        with open("data/watchdog.pid", "w") as f:
            f.write(str(pid))
        logger.info(f"Watchdog PID {pid} recorded to data/watchdog.pid")
    except Exception as e:
        logger.error(f"Failed to write Watchdog PID: {e}")

def run_watchdog():
    _write_watchdog_pid()
    logger.info("Sovereign Dead-Man Watchdog ACTIVE.")
    logger.info(
        f"Monitoring {DB_PATH} every {CHECK_INTERVAL}s | "
        f"Silence threshold: {SILENCE_TIMEOUT}s | Live-lock threshold: {LIVENESS_TIMEOUT}s"
    )

    import subprocess
    
    while True:
        try:
            is_alive = check_heartbeat()
            stale = check_task_liveness()
            mem_usage = check_memory_usage()
            
            mem_limit = get_dynamic_memory_threshold()
            should_restart = not is_alive or stale or (mem_usage > mem_limit)
            
            if mem_usage > mem_limit:
                logger.critical(f"MEMORY DEPLETION DETECTED: Engine consuming {mem_usage:.1f}MB (Threshold: {mem_limit:.1f}MB)")

            if should_restart:
                # GAP-24 FIX: Throttled Restart with Exponential Backoff
                now = time.time()
                recent_restarts = [t for t in restart_history if now - t < 3600] # 60 min window
                
                # Dynamic Exponential Backoff: 1m, 5m, 15m, 60m
                attempts = len(recent_restarts)
                wait_time = 0
                if attempts == 1: wait_time = 60
                elif attempts == 2: wait_time = 300
                elif attempts == 3: wait_time = 900
                elif attempts >= 4: wait_time = 3600
                
                last_restart = max(restart_history) if restart_history else 0
                
                if now - last_restart < wait_time:
                    logger.warning(f"RESTART THROTTLED (GAP-24): Backoff active. Next attempt in {wait_time - (now - last_restart):.0f}s.")
                    should_restart = False
                
                if should_restart:
                    if len(recent_restarts) >= 6: # Hard panic
                         logger.critical("🚨 WATCHDOG PANIC: Excessive restarts (6+) in 1h. SYSTEM HALTED to protect account.")
                         should_restart = False 
                    
                    if should_restart:
                        logger.critical(f"EMERGENCY RESTART INITIATED (Attempt {len(recent_restarts)+1}): Clearing ghosts...")
                        restart_history.add(now)
                        
                        # --- KILL THE GHOSTS ---
                        pid_file = "data/main.pid"
                        pid_to_kill = None
                        if os.path.exists(pid_file):
                            try:
                                with open(pid_file, "r") as f:
                                    pid_to_kill = f.read().strip()
                            except Exception: pass
                        
                        if pid_to_kill:
                            try:
                                logger.info(f"Watchdog: Terminating stale main process (PID: {pid_to_kill})...")
                                subprocess.run(["taskkill", "/F", "/PID", pid_to_kill], capture_output=True)
                                # GAP-94: Increased graceful wait for port release
                                logger.info("Watchdog: Waiting 10s for port release (GAP-94)...")
                                time.sleep(10) 
                            except Exception as e:
                                logger.error(f"Watchdog: Failed to kill process {pid_to_kill}: {e}")

                        # --- SPAWN THE NEW SOVEREIGN ---
                        subprocess.Popen([sys.executable, "src/main.py"], cwd=os.getcwd())
                        logger.info("Watchdog: Sovereign Engine REBOOTED.")
                else:
                    logger.warning(f"RESTART THROTTLED: Next attempt in {wait_time - (now - last_restart):.0f}s.")

            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Watchdog shutting down.")
            break


if __name__ == "__main__":
    run_watchdog()
