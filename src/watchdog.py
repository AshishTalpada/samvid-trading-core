import atexit
import logging
from logging.handlers import RotatingFileHandler
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Setup minimal logging. The main process launches this helper detached with
# stdout/stderr hidden, so a file sink is required for post-mortem visibility.
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
_formatter = logging.Formatter("%(asctime)s - WATCHDOG - %(levelname)s - %(message)s")
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_formatter)
_file_handler = RotatingFileHandler(
    LOG_DIR / "watchdog.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8"
)
_file_handler.setFormatter(_formatter)
logging.basicConfig(level=logging.INFO, handlers=[_console_handler, _file_handler])
logger = logging.getLogger(__name__)

DB_PATH = "data/trading.db"
CHECK_INTERVAL = 30  # Check every 30 seconds (tightened from 60)
LIVENESS_TIMEOUT = 120  # Task is live-locked if heartbeat > 120s stale
SILENCE_TIMEOUT = 60  # System crashed if > 60s total silence (matches DMS)
MEMORY_THRESHOLD_MB = 1200


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


def _remove_pid_file(path: str, expected_pid: str | None = None) -> None:
    """Remove a stale PID file, optionally only if it still contains expected_pid."""
    try:
        if not os.path.exists(path):
            return
        if expected_pid is not None:
            with open(path, "r") as f:
                current = f.read().strip()
            if current != expected_pid:
                return
        os.remove(path)
        logger.info("Watchdog: Removed stale PID file %s.", path)
    except Exception as exc:
        logger.debug("Watchdog: PID cleanup skipped for %s: %s", path, exc)


def check_heartbeat(watchdog_start_time: datetime) -> bool:
    """Returns True if the system is alive, False if silent/crashed."""
    if not os.path.exists(DB_PATH):
        logger.warning(f"Database {DB_PATH} not found. Waiting...")
        return True

    try:
        with sqlite3.connect(DB_PATH, timeout=60.0) as conn:
            conn.execute("PRAGMA busy_timeout=60000;")
            cursor = conn.cursor()

            # Check system status and heartbeat together. A prior clean shutdown
            # can leave system_status='stopped' in SQLite; treating that stale
            # value as live truth makes freshly spawned watchdogs kill themselves.
            cursor.execute("SELECT value FROM system_state WHERE key='system_status'")
            status_row = cursor.fetchone()
            cursor.execute("SELECT value FROM system_state WHERE key='last_heartbeat'")
            row = cursor.fetchone()

        if row:
            last_hb_str = row[0]
            last_hb = _parse_heartbeat_value(last_hb_str)
            if last_hb is None:
                logger.warning("Invalid heartbeat value found in database: %r", last_hb_str)
                return True

            if status_row and status_row[0] == "stopped":
                if last_hb >= watchdog_start_time:
                    logger.info("Watchdog: Main engine stopped gracefully. Terminating watchdog.")
                    sys.exit(0)
                logger.info("Watchdog: Ignoring stale stopped state from prior session.")

            # Ignore legacy heartbeat from prior sessions during initial phase
            if last_hb < watchdog_start_time:
                seconds_since_start = (
                    datetime.now(timezone.utc) - watchdog_start_time
                ).total_seconds()
                if seconds_since_start > 120:
                    logger.critical(
                        f"SYSTEM STARTUP SILENCE DETECTED! No heartbeat written since watchdog started "
                        f"{seconds_since_start:.1f}s ago. Main engine may have failed during startup."
                    )
                    return False
                logger.info(
                    f"Prior session heartbeat ignored. Waiting for startup... ({seconds_since_start:.1f}s elapsed)"
                )
                return True

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


def _parse_heartbeat_value(value: object) -> datetime | None:
    """Parse legacy ISO heartbeats and current nanosecond epoch heartbeats."""
    if value is None:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    try:
        if raw.isdigit():
            number = int(raw)
            if number > 10_000_000_000_000_000:
                return datetime.fromtimestamp(number / 1_000_000_000, tz=timezone.utc)
            return datetime.fromtimestamp(number, tz=timezone.utc)

        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed
    except (OSError, ValueError, OverflowError):
        return None


def check_task_liveness(watchdog_start_time: datetime) -> dict:
    """
    Fix 14: Detects live-locked tasks by reading per-task heartbeat timestamps.
    A task is considered live-locked if it hasn't written a heartbeat in LIVENESS_TIMEOUT seconds.
    """
    import json

    stale_tasks = {}
    if not os.path.exists(TASK_HEARTBEAT_FILE):
        return stale_tasks
    try:
        file_mtime = os.path.getmtime(TASK_HEARTBEAT_FILE)
        if file_mtime < watchdog_start_time.timestamp():
            logger.info("Watchdog: Ignoring task heartbeat registry from prior session.")
            return stale_tasks

        with open(TASK_HEARTBEAT_FILE, "r") as f:
            payload = json.load(f)
        if isinstance(payload, dict) and "heartbeats" in payload:
            heartbeats = payload.get("heartbeats") or {}
        else:
            heartbeats = payload

        if not isinstance(heartbeats, dict):
            logger.warning("Watchdog: Invalid task heartbeat registry shape.")
            return stale_tasks

        now = time.time()
        for task_name, last_ts in heartbeats.items():
            heartbeat_ts = float(last_ts)
            if heartbeat_ts < watchdog_start_time.timestamp():
                continue
            age = now - heartbeat_ts
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

        # If the main.pid file is missing, we attempt to find the process by name
        pid_file = "data/main.pid"
        target_pid = None

        if os.path.exists(pid_file):
            try:
                with open(pid_file, "r") as f:
                    target_pid = int(f.read().strip())
            except Exception:
                pass

        if not target_pid or not psutil.pid_exists(target_pid):
            if target_pid:
                _remove_pid_file(pid_file, str(target_pid))
            # Fallback: Find by process name if file is missing/stale
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                if "python" in (proc.info["name"] or "").lower():
                    cmdline = proc.info["cmdline"] or []
                    if any("src/main.py" in arg for arg in cmdline):
                        target_pid = proc.info["pid"]
                        logger.info(
                            f"Watchdog: Ghost PID {target_pid} discovered via process scan."
                        )
                        break

        if target_pid and psutil.pid_exists(target_pid):
            target_process = psutil.Process(target_pid)
            return target_process.memory_info().rss / (1024 * 1024)

        return 0.0
    except Exception as e:
        logger.error(f"Watchdog: Memory check failed: {e}")
        return 0.0


from typing import Set

restart_history: Set[float] = set()


def _write_watchdog_pid() -> None:
    """Record Watchdog PID for the main engine to verify connectivity."""
    try:
        pid = os.getpid()
        os.makedirs("data", exist_ok=True)
        with open("data/watchdog.pid", "w") as f:
            f.write(str(pid))
        atexit.register(_remove_pid_file, "data/watchdog.pid", str(pid))
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

    monitored_engine_start_time = datetime.now(timezone.utc)
    monitored_engine_start_ts = time.time()

    while True:
        try:
            uptime = time.time() - monitored_engine_start_ts
            if uptime < 90:
                logger.info(f"Watchdog startup grace period: {90 - uptime:.0f}s remaining...")
                time.sleep(CHECK_INTERVAL)
                continue

            is_alive = check_heartbeat(monitored_engine_start_time)
            stale = check_task_liveness(monitored_engine_start_time)
            mem_usage = check_memory_usage()

            mem_limit = get_dynamic_memory_threshold()
            should_restart = not is_alive or stale or (mem_usage > mem_limit)

            if mem_usage > mem_limit:
                logger.critical(
                    f"MEMORY DEPLETION DETECTED: Engine consuming {mem_usage:.1f}MB "
                    f"(Threshold: {mem_limit:.1f}MB)"
                )

            if should_restart:
                now = time.time()
                recent_restarts = [t for t in restart_history if now - t < 3600]  # 60 min window

                # Dynamic Exponential Backoff: 1m, 5m, 15m, 60m
                attempts = len(recent_restarts)
                wait_time = 0
                if attempts == 1:
                    wait_time = 60
                elif attempts == 2:
                    wait_time = 300
                elif attempts == 3:
                    wait_time = 900
                elif attempts >= 4:
                    wait_time = 3600

                last_restart = max(restart_history) if restart_history else 0

                if now - last_restart < wait_time:
                    logger.warning(
                        f"RESTART THROTTLED: Backoff active. Next attempt in "
                        f"{wait_time - (now - last_restart):.0f}s."
                    )
                    should_restart = False

                if should_restart:
                    if len(recent_restarts) >= 6:  # Hard panic
                        logger.critical(
                            " WATCHDOG PANIC: Excessive restarts (6+) in 1h. "
                            "SYSTEM HALTED to protect account."
                        )
                        should_restart = False

                    if should_restart:
                        logger.critical(
                            f"EMERGENCY RESTART INITIATED (Attempt "
                            f"{len(recent_restarts) + 1}): Clearing ghosts..."
                        )
                        restart_history.add(now)

                        pid_file = "data/main.pid"
                        pid_to_kill = None
                        if os.path.exists(pid_file):
                            try:
                                with open(pid_file, "r") as f:
                                    pid_to_kill = f.read().strip()
                            except Exception as exc:
                                logger.debug(
                                    "Watchdog: Failed to read PID file %s: %s", pid_file, exc
                                )

                        if pid_to_kill and pid_to_kill.isdigit():
                            try:
                                logger.info(
                                    "Watchdog: Terminating stale main process "
                                    f"(PID: {pid_to_kill})..."
                                )
                                subprocess.run(
                                    ["taskkill", "/F", "/PID", pid_to_kill],
                                    capture_output=True,
                                    check=True,
                                )
                                logger.info("Watchdog: Waiting 10s for port release...")
                                time.sleep(10)
                            except Exception as e:
                                logger.error(f"Watchdog: Failed to kill process {pid_to_kill}: {e}")
                            finally:
                                _remove_pid_file(pid_file, pid_to_kill)
                        elif pid_to_kill:
                            logger.warning(
                                "Watchdog: Ignoring invalid PID file content: %r", pid_to_kill
                            )
                            _remove_pid_file(pid_file, pid_to_kill)

                        project_root = Path(__file__).resolve().parent.parent
                        main_script = project_root / "src" / "main.py"
                        if not main_script.exists():
                            logger.critical("Watchdog: Cannot reboot, missing %s", main_script)
                            continue

                        creationflags = 0
                        startupinfo = None
                        if sys.platform == "win32":
                            creationflags = (
                                subprocess.CREATE_NEW_PROCESS_GROUP
                                | subprocess.CREATE_NO_WINDOW
                            )
                            startupinfo = subprocess.STARTUPINFO()
                            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

                        reboot_proc = subprocess.Popen(
                            [sys.executable, str(main_script)],
                            cwd=str(project_root),
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            close_fds=os.name != "nt",
                            creationflags=creationflags,
                            startupinfo=startupinfo,
                        )
                        logger.info(
                            "Watchdog: Sovereign Engine REBOOTED as PID %s.", reboot_proc.pid
                        )
                        monitored_engine_start_time = datetime.now(timezone.utc)
                        monitored_engine_start_ts = time.time()
                        # main.py owns data/main.pid after it passes the
                        # single-instance guard. Writing the child PID here can
                        # make a half-started reboot look like the active engine
                        # and cause duplicate-instance false positives.
                else:
                    logger.warning(
                        f"RESTART THROTTLED: Next attempt in "
                        f"{wait_time - (now - last_restart):.0f}s."
                    )

            time.sleep(CHECK_INTERVAL)
        except KeyboardInterrupt:
            logger.info("Watchdog shutting down.")
            break


if __name__ == "__main__":
    run_watchdog()
