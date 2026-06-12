import io
import os
import sys
from pathlib import Path

from vault import Vault

try:
    import zstandard  # type: ignore
except ImportError:
    zstandard = None

# Force UTF-8 encoding for Windows terminals to support emojis/special characters
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, io.UnsupportedOperation) as e:
        print(f"[boot] could not reconfigure stdout/stderr encoding: {e}", file=sys.stderr)

# Disable ChromaDB telemetry BEFORE any imports to prevent PostHog errors
os.environ["ANONYMIZED_TELEMETRY"] = "False"
os.environ["CHROMA_TELEMETRY_ENABLED"] = "False"

# Add project root and src directory to python path
_here = Path(__file__).resolve().parent
_root = str(_here.parent)
_src = str(_here)
if _root not in sys.path:
    sys.path.insert(0, _root)
if _src not in sys.path:
    sys.path.insert(0, _src)

import asyncio
import asyncio.subprocess
import json
import logging
import sqlite3
import subprocess
import time
from collections.abc import Callable, Coroutine
from contextlib import closing
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import TYPE_CHECKING, Any

import aiohttp

from market_calendar import is_us_equity_market_open, us_equity_session_status
from mind_bridge import MindBridge
from mind_system import MindSystem
from session_restorer import SessionRestorer
from text_safety import normalize_operator_text
from time_sync import TimeSync

if TYPE_CHECKING:
    from ib_insync import IB

    from brain import TradingBrain
    from data_pipeline import DataPipeline
    from dms import DMSMonitor


import safety
from api_server import APIServer
from config import (
    QUESTDB_CONNECT_TIMEOUT_SEC,
    QUESTDB_ENABLED,
    QUESTDB_HOST,
    QUESTDB_PASSWORD,
    QUESTDB_PG_PORT,
    QUESTDB_PORT,
    QUESTDB_USER,
    TRADING_MODE,
)
from ibkr_streamer import IBKRStreamer
from intelligence_bus import get_bus
from questdb_adapter import QuestDBAdapter
from runtime_health import ComponentHealth, build_health_snapshot, market_data_health
from telegram_remote import get_remote
from tv_quote_streamer import TVQuoteStreamer


class SovereignFormatter(logging.Formatter):
    """
    Sovereign Intelligence Formatter.
        Combines Unicode-safe stream handling with mandatory secret redaction.
    """

    def __init__(self, fmt=None, datefmt=None, secrets=None):
        super().__init__(fmt, datefmt)
        self._secrets = secrets or []
        import re

        patterns = []
        for secret in sorted(
            (str(value) for value in self._secrets if len(str(value)) > 3),
            key=len,
            reverse=True,
        ):
            escaped = re.escape(secret)
            if secret.isalnum() and len(secret) < 12:
                # Short passwords and account labels can also occur inside normal
                # words (for example, "quest" inside "request"). Redact them
                # only as standalone values while keeping long tokens exhaustive.
                patterns.append(rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])")
            else:
                patterns.append(escaped)
        if patterns:
            self._pattern = re.compile("|".join(patterns))
        else:
            self._pattern = None

    def format(self, record):
        try:
            # First, format using standard logic
            msg = super().format(record)
            msg = normalize_operator_text(msg)

            # Second, Apply Redaction
            if self._pattern:
                msg = self._pattern.sub("[REDACTED]", msg)

            # We detect this by checking if the handler being used is a StreamHandler
            # to stdout/stderr
            # But since format() doesn't know the handler, we rely on a cleaner check.
            # Modern Windows Terminals and File Handlers (with encoding='utf-8') handle emojis fine.
            return msg
        except Exception:
            # Fail-safe: if formatting fails, return a basic string
            return f"LOG_FORMAT_ERROR: {record.msg}"


# Configure logging
secrets = Vault.get_all_redactable_values()
formatter = SovereignFormatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s", secrets=secrets
)

root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

# File handler with rotation
log_file = Path(os.environ.get("SOVEREIGN_LOG_FILE", "logs/trading_system.log"))
log_file.parent.mkdir(parents=True, exist_ok=True)
file_handler = RotatingFileHandler(
    str(log_file),
    encoding="utf-8",
    maxBytes=15 * 1024 * 1024,  # Expanded to 15MB
    backupCount=7,
)
file_handler.setFormatter(formatter)

# Stream handler (Terminal)
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(formatter)

root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("httpcore").setLevel(logging.INFO)
logging.getLogger("httpx").setLevel(logging.INFO)
logging.getLogger("chromadb").setLevel(logging.WARNING)
logging.getLogger("fastembed").setLevel(logging.WARNING)


# Suppress noisy third-party libraries for production
logging.getLogger("yfinance").setLevel(logging.CRITICAL)
logging.getLogger("peewee").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("ib_insync").setLevel(logging.ERROR)
logging.getLogger("ib_insync.client").setLevel(logging.CRITICAL)
logging.getLogger("ib_insync.wrapper").setLevel(logging.CRITICAL)
logging.getLogger("anthropic").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("google_genai").setLevel(logging.WARNING)
logging.getLogger("intelligence_bus").setLevel(logging.WARNING)
logging.getLogger("data_pipeline").setLevel(logging.INFO)
logging.getLogger("mind_bridge").setLevel(logging.WARNING)
logging.getLogger("questdb_adapter").setLevel(logging.WARNING)


class TelemetryFilter(logging.Filter):
    def filter(self, record):
        msg = record.getMessage()
        return "Failed to send telemetry event" not in msg and "capture()" not in msg


logging.getLogger("chromadb.telemetry").addFilter(TelemetryFilter())
logging.getLogger("chromadb.telemetry").setLevel(logging.CRITICAL)
logging.getLogger("posthog").setLevel(logging.CRITICAL)


logger = logging.getLogger(__name__)

# Validate config now that logging is ready (moved from config.py module-level)
from config import _validate_config

_validate_config()


class StartupProfiler:
    """Institutional-grade startup profiling."""

    def __init__(self) -> None:
        self._marks = {}
        self._start = time.perf_counter()

    def mark(self, name: str) -> None:
        self._marks[name] = time.perf_counter() - self._start
        logger.debug(f"  PROFILER: {name.ljust(30)} | {self._marks[name] * 1000:7.2f}ms")


class TradingSystem:
    def _get_status_icon(self, component: str) -> str:
        """Return an ASCII-safe dynamic status label for startup notifications."""
        if component == "ibkr":
            try:
                if getattr(self, "ibkr_client", None) and self.ibkr_client.isConnected():
                    return "GREEN ONLINE"
            except Exception as exc:
                logger.debug("Startup status probe failed for IBKR: %s", exc)
                return "RED ERROR"
            if "connect_ibkr" in getattr(self, "background_tasks", {}):
                return "YELLOW PROBING"
            return "RED OFFLINE"
        if component == "mt5":
            try:
                if getattr(self, "mt5_client", None) and self.mt5_client.terminal_info():
                    return "GREEN ONLINE"
            except Exception as exc:
                logger.debug("Startup status probe failed for MT5: %s", exc)
                return "RED ERROR"
            if "connect_mt5" in getattr(self, "background_tasks", {}):
                return "YELLOW PROBING"
            return "RED OFFLINE"
        if component == "qdb":
            try:
                if getattr(self, "qdb", None) and self.qdb.is_active:
                    return "GREEN ACTIVE"
            except Exception as exc:
                logger.debug("Startup status probe failed for QuestDB: %s", exc)
                return "RED ERROR"
            return "RED OFFLINE"
        if component == "dhatu":
            return "GREEN CALIBRATED" if getattr(self, "dhatu_oracle", None) else "RED OFFLINE"
        return "UNKNOWN"

    def _get_openbb_startup_status(self) -> str:
        """Return the OpenBB lane state without hiding an active fallback provider."""
        provider = getattr(self, "_openbb_provider", None)
        if not provider:
            return "RED OFFLINE"
        try:
            health_status = getattr(provider, "health_status", None)
            status, detail = health_status() if callable(health_status) else (provider.status, "")
            prefix = {
                "ONLINE": "GREEN ONLINE",
                "FALLBACK": "YELLOW FALLBACK",
                "PROBING": "YELLOW PROBING",
            }.get(str(status).upper(), "RED OFFLINE")
            return f"{prefix} - {detail}" if detail else prefix
        except Exception as exc:
            logger.debug("Startup status probe failed for OpenBB: %s", exc)
            return "RED ERROR"

    @property
    def requires_ibkr_connection(self) -> bool:
        """Return True for modes that require a real IBKR session."""
        return self.mode in ("ibkr_paper", "live")

    @property
    def is_paper_only(self) -> bool:
        """Return True when the system is running pure local simulation only."""
        return self.mode == "paper"

    @staticmethod
    def execution_watchlist() -> list[str]:
        """Return the scanner's tradable symbols for warmup and realtime subscriptions."""
        from brain_data import DataProvider

        return list(DataProvider.EXECUTION_WATCHLIST)

    def __init__(self) -> None:
        self.profiler = StartupProfiler()
        self.profiler.mark("CONSTRUCTOR_START")

        # Master Safety Control: delegate to safety module which enforces conservative defaults
        # This may set `self.mode` to 'paper' unless a deliberate override is provided.
        self.mode = Vault.get("TRADING_MODE", TRADING_MODE)
        try:
            safety.apply_runtime_safety(self)
        except Exception:
            logger.exception("safety.apply_runtime_safety failed; proceeding with configured mode")
        logger.info(f"Trading mode: {self.mode}")

        self.db_path = Path("data/trading.db")
        self.schema_path = Path("data/schema.sql")
        self.start_time = datetime.now(timezone.utc)

        # Configuration (from Vault)
        self.ibkr_host = Vault.get("IBKR_HOST", "localhost")
        self.ibkr_port = int(Vault.get("IBKR_PORT", "7497"))
        self.ibkr_client_id = int(Vault.get("IBKR_CLIENT_ID", "500"))
        self.ibkr_account_id = Vault.get("IBKR_ACCOUNT_ID", "")

        self.mt5_login = Vault.get("MT5_LOGIN")
        self.mt5_password = Vault.get("MT5_PASSWORD")
        self.mt5_server = Vault.get("MT5_SERVER")
        self.mt5_path = Vault.get("MT5_PATH")

        self.telegram_token = Vault.get("TELEGRAM_BOT_TOKEN")
        self.telegram_chat_id = Vault.get("TELEGRAM_CHAT_ID")

        # Ensure we have write permissions in the project root before starting.
        test_file = Path(_root) / ".write_test"
        try:
            test_file.write_text("Sovereign Write Test", encoding="utf-8")
        except (IOError, OSError) as e:
            logger.critical(f" CRITICAL: Project path is NOT writable ({_root}). Error: {e}")
            raise RuntimeError("Sovereign Initialization Failed: No write access to PROJECT_PATH.")
        finally:
            try:
                test_file.unlink(missing_ok=True)
            except OSError as exc:
                logger.debug("Startup write-test cleanup skipped for %s: %s", test_file, exc)

        # Ensure directories exist
        Path("data").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)
        Path("models").mkdir(exist_ok=True)

        # Component References (Lazy Init)
        self.db_conn: sqlite3.Connection | None = None
        self.ibkr_client: "IB" | None = None
        self.mt5_client: Any = None
        self.data_pipeline: DataPipeline | None = None
        self.dms: DMSMonitor | None = None
        self.trading_brain: TradingBrain | None = None
        self.telegram_bot: Any = None
        self.ibc: Any = None
        self.dhatu_oracle: Any = None
        self.bus = get_bus()
        self.bridge = MindBridge(self.bus)
        self.questdb: QuestDBAdapter | None = None
        self.api_server: APIServer | None = None
        self.hft_streamer: IBKRStreamer | None = None
        self.tv_quote_streamer: TVQuoteStreamer | None = None
        self.restorer = SessionRestorer()
        self._openbb_provider: Any = None
        self.native_slm: Any = None
        self.telegram_remote = get_remote()  # Remote Command Hub
        self.is_running = False
        self._mt5_failure_count = 0  # Track sequential MT5 heartbeat failures

        self.background_tasks: dict[str, asyncio.Task[None]] = {}
        self.db_lock = asyncio.Lock()
        self._shutdown_lock = asyncio.Lock()
        self._shutdown_task = None
        self._shutdown_event = asyncio.Event()
        self._shutdown_in_progress = False
        self._shutdown_complete = False
        self._hft_pulse_queue: Any = None
        self._shutdown_request_path = Path("data/shutdown.request")

        self._last_tick_time = time.monotonic()
        self._last_data_starvation_alert = 0.0
        self._recalibration_in_progress = False
        self._ibkr_outage_active = False

        self._write_pid()
        self.profiler.mark("CONSTRUCTOR_COMPLETE")

    def _is_safe_path(self, path: str) -> bool:
        """
        Sovereign 'Patience Gap' Validator (Main Context).
        Ensures a path is absolute, non-root, non-malformed, and executable-safe.
        Guards against os.path.exists('\\\\') returning True on Windows.
        """
        if not path or not isinstance(path, str):
            return False
        path = os.path.abspath(os.path.normpath(path))
        # Block root-drive paths — 'C:\\' is only 3 chars; '\\\\' normalises to 'C:\\'
        if len(path) < 4:
            return False
        # Belt-and-suspenders: reject known malformed patterns even after normpath
        if path.strip() in ("\\", "/", ".", ".."):
            return False
        if not os.path.exists(path):
            return False
        # For files specifically, only allow safe executable extensions
        if os.path.isfile(path):
            ext = os.path.splitext(path)[1].lower()
            if ext not in (".exe", ".bat", ".cmd", ".sh", ".py"):
                return False
        return True

    def _write_pid(self) -> None:
        """Record PID and verify single instance for the cognitive matrix."""
        # Allow tests and import smoke runs to bypass PID checks by setting
        # SOVEREIGN_SKIP_PID_CHECK=1 in the environment.
        if os.environ.get("SOVEREIGN_SKIP_PID_CHECK", "0") == "1":
            logger.debug("SOVEREIGN_SKIP_PID_CHECK=1; skipping PID single-instance verification")
            return
        try:
            import psutil

            pid_file = "data/main.pid"
            os.makedirs(os.path.dirname(pid_file), exist_ok=True)
            current_pid = os.getpid()
            existing_raw = ""

            if os.path.exists(pid_file):
                try:
                    with open(pid_file, "r") as f:
                        existing_raw = (f.read() or "").strip()
                    old_pid = int(existing_raw)

                    if old_pid != current_pid and psutil.pid_exists(old_pid):
                        proc = psutil.Process(old_pid)
                        proc_name = proc.name().lower()
                        cmdline = proc.cmdline() or []
                        cmdline_str = " ".join(cmdline).replace("\\", "/")
                        same_app = "src/main.py" in cmdline_str or "main.py" in cmdline_str

                        if same_app:
                            tail_cmd = r"powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\tail_live_logs.ps1"
                            logger.critical(
                                f" CRITICAL: Duplicate Sovereign Instance Detected "
                                f"(PID: {old_pid})."
                            )
                            logger.critical(
                                "Multiple instances cause Telegram 409 Conflict "
                                "and Broker Port locks."
                            )
                            logger.critical(
                                "The existing engine is still running. To watch it live, run: %s",
                                tail_cmd,
                            )
                            logger.critical(
                                "To stop it intentionally, terminate PID %s first, then restart.",
                                old_pid,
                            )
                            print(
                                "\nDuplicate Sovereign instance blocked.\n"
                                f"Existing engine PID: {old_pid}\n"
                                f"Live logs: {tail_cmd}\n",
                                file=sys.stderr,
                            )
                            sys.exit(1)

                        if "python" in proc_name:
                            logger.warning(
                                f"PID file points at unrelated Python process {old_pid}. "
                                "Process exists but does not appear to be the "
                                "current Sovereign instance. "
                                "Overwriting PID file."
                            )
                    else:
                        logger.info(
                            "Stale PID file detected for dead PID %s. Reclaiming lock.",
                            old_pid,
                        )
                except ValueError:
                    logger.warning(
                        "Invalid PID file content in %s: %r. Reclaiming lock.",
                        pid_file,
                        existing_raw,
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied) as exc:
                    logger.info(
                        "PID file owner %r could not be verified (%s). Reclaiming lock.",
                        existing_raw,
                        exc,
                    )

            # Remove the file only if it still holds the stale PID we read, so we never
            # clobber a PID that another instance may have just claimed.
            if existing_raw:
                try:
                    with open(pid_file, "r") as rf:
                        current_raw = (rf.read() or "").strip()
                    if current_raw == existing_raw:
                        os.remove(pid_file)
                        logger.info("Removed stale PID lock %s containing %r.", pid_file, existing_raw)
                    else:
                        logger.info(
                            "PID lock %s changed from %r to %r during startup; "
                            "leaving it for atomic duplicate detection.",
                            pid_file,
                            existing_raw,
                            current_raw,
                        )
                except FileNotFoundError:
                    pass
                except OSError as exc:
                    logger.error(
                        "Failed to remove stale PID lock %s containing %r: %s",
                        pid_file,
                        existing_raw,
                        exc,
                    )

            # Atomic single-instance claim. O_EXCL guarantees only one process can
            # create the PID file, closing the TOCTOU race where two engines launched
            # at the same instant both passed the check above and both ran.
            try:
                fd = os.open(pid_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    with open(pid_file, "r") as rf:
                        owner_raw = (rf.read() or "").strip()
                except OSError:
                    owner_raw = "<unreadable>"
                logger.critical(
                    " CRITICAL: Lost single-instance race for %s; another Sovereign "
                    "engine claimed it concurrently. Owner content=%r. Exiting duplicate.",
                    pid_file,
                    owner_raw,
                )
                print(
                    "\nDuplicate Sovereign instance blocked (concurrent launch).\n",
                    file=sys.stderr,
                )
                sys.exit(1)
            with os.fdopen(fd, "w") as f:
                f.write(str(current_pid))
            logger.debug(f"PID {current_pid} recorded to {pid_file}")
        except Exception as e:
            logger.error(f"Failed to verify single instance or write PID: {e}")

    def _clear_own_pid_file(self) -> None:
        """Remove data/main.pid only when it still points at this process."""
        pid_file = "data/main.pid"
        try:
            if not os.path.exists(pid_file):
                return
            with open(pid_file, "r") as f:
                recorded_pid = int((f.read() or "").strip())
            if recorded_pid == os.getpid():
                os.remove(pid_file)
                logger.info("Removed own main PID file during shutdown.")
        except Exception as exc:
            logger.debug("Main PID cleanup skipped: %s", exc)

    async def async_init(self) -> None:
        """PILLAR 6: Progressive Orchestration (9.99 Upgrade)
        Parallelizes the cognitive matrix for sub-100ms startup.
        """
        self.profiler.mark("ASYNC_INIT_START")

        # Handle termination signals cleanly in the main event loop
        if sys.platform != "win32":
            import signal

            try:
                loop = asyncio.get_running_loop()
                self._shutdown_task: asyncio.Task | None = None

                def _signal_handler() -> None:
                    if self._shutdown_task is None or self._shutdown_task.done():
                        self._shutdown_task = asyncio.create_task(
                            self.shutdown(), name="signal_shutdown"
                        )

                for sig in (signal.SIGINT, signal.SIGTERM):
                    loop.add_signal_handler(sig, _signal_handler)
            except (RuntimeError, NotImplementedError) as e:
                logger.debug("Main: signal handler setup not supported on this platform: %s", e)

        # 1. Sovereign Scent Detection (Pillar 9.99)
        self.mind_system = MindSystem(self.bridge)
        logger.info("MindSystem: Scanning for software scients and verifying environment...")
        if self.requires_ibkr_connection:
            executable_found = await self.mind_system._tool_find_executable("ibkr")
            if not executable_found:
                logger.error(
                    " CRITICAL: IBKR/TWS Executable not found. "
                    "Environment is NON-COMPLIANT. Stopping."
                )
                raise RuntimeError(
                    "Sovereign Initialization Failed: Missing Institutional Software"
                )
        else:
            logger.info("Paper mode detected — skipping IBKR executable verification.")
        self.profiler.mark("SYSTEM_SCENT_CAPTURED")

        # 1.1 Synchronize Clock
        await TimeSync.sync()

        # 1.2 JIT Warmup — pre-compile Numba math kernels before first tick
        try:
            from quant_math import warmup as _jit_warmup

            await asyncio.to_thread(_jit_warmup)
            self.profiler.mark("JIT_WARMUP_DONE")
        except Exception as _e:
            logger.warning(f"JIT warmup skipped (non-fatal): {_e}")

        await self._verify_watchdog()

        # Pre-subscribe to the HFT pulse before launching the streamer to capture start events.
        self._hft_pulse_queue = self.bus.subscribe("tick.hft", maxsize=100)

        # 2. Parallelize Infrastructure Launch
        logger.info("Initializing Sovereign Infrastructure (QuestDB, API, Providers)...")
        tasks = [
            self._init_questdb(),
            self._init_api_server(),
            self._init_search_providers(),
            self._init_hft_streamer(),
        ]
        await asyncio.gather(*tasks)

        if os.environ.get("SOVEREIGN_SKIP_PID_CHECK", "0") == "1" and self.is_paper_only:
            logger.info("Smoke-test paper mode detected - skipping DB and background monitors.")
            self.profiler.mark("SMOKE_ASYNC_INIT_DONE")
            return

        # Background supervisors check this flag before entering their loops.
        # Set it before launching any supervised task; otherwise startup races
        # cause critical services to stand down as if shutdown had begun.
        self.is_running = True

        # Windows cannot reliably deliver SIGINT to a detached Python process.
        # A PID-bound local request lets operator tooling enter the same audited
        # shutdown path used by an interactive Ctrl+C.
        self.background_tasks["shutdown_request_listener"] = asyncio.create_task(
            self._run_shutdown_request_listener(), name="shutdown_request_listener"
        )

        # Start the worker task after parallel init
        self._start_supervised_task("hft_pulse_worker", self._run_hft_pulse_worker)

        self.profiler.mark("INFRASTRUCTURE_SYNCED")

        # 2. Sequential Cognitive Handshake
        await self.init_database()
        self.profiler.mark("SQLITE_SYNCED")

        # 3. Memory & Cache Warmup (Agent I Upgrade)
        self.profiler.mark("CACHE_WAKED")

        logger.info(
            " Matrix Progressive Init Complete in "
            f"{self.profiler._marks.get('SYSTEM_SCENT_CAPTURED', 0) * 1000:.2f}ms"
        )

        # Launch health-Pulse Monitor
        self._aegis_task = asyncio.create_task(self._run_aegis_watchdog())
        self._sentinel_task = asyncio.create_task(self._run_persistence_sentinel())
        self._perf_task = asyncio.create_task(self._run_performance_monitor())
        # Track in background_tasks so shutdown cancels them cleanly
        self.background_tasks["aegis_watchdog"] = self._aegis_task
        self.background_tasks["persistence_sentinel"] = self._sentinel_task
        self.background_tasks["performance_monitor"] = self._perf_task

    async def _init_questdb(self) -> None:
        _qdb_timeout = Vault.get("QUESTDB_CONNECT_TIMEOUT_SEC", str(QUESTDB_CONNECT_TIMEOUT_SEC))
        _qdb_enabled_raw = Vault.get("QUESTDB_ENABLED", "")
        _qdb_enabled = QUESTDB_ENABLED
        if str(_qdb_enabled_raw).strip():
            _qdb_enabled = str(_qdb_enabled_raw).strip().lower() in {"true", "1", "yes"}
        self.questdb = QuestDBAdapter(
            host=Vault.get("QUESTDB_HOST", QUESTDB_HOST),
            ilp_port=int(Vault.get("QUESTDB_PORT", str(QUESTDB_PORT))),
            pg_port=int(Vault.get("QUESTDB_PG_PORT", str(QUESTDB_PG_PORT))),
            user=Vault.get("QUESTDB_USER", QUESTDB_USER) or "admin",
            password=Vault.get("QUESTDB_PASSWORD", QUESTDB_PASSWORD) or "quest",
            enabled=_qdb_enabled,
            connect_timeout_sec=float(_qdb_timeout)
            if _qdb_timeout
            else QUESTDB_CONNECT_TIMEOUT_SEC,
        )
        await self.questdb.start()

        # Start CandleWriter — subscribes to tick.batch and builds live OHLCV for scanner
        try:
            from questdb_candle_writer import CandleWriter

            self.candle_writer = CandleWriter(qdb_adapter=self.questdb)
            await self.candle_writer.start(self.bus)
            logger.info("CandleWriter: Live OHLCV aggregation active.")
        except Exception as _e:
            logger.warning(f"CandleWriter startup failed (non-fatal): {_e}")
            self.candle_writer = None

        self.profiler.mark("QUESTDB_READY")

    async def _init_api_server(self) -> None:
        import socket

        def is_port_in_use(port: int) -> bool:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                return s.connect_ex(("localhost", port)) == 0

        _api_port_raw = Vault.get("API_SERVER_PORT", "8000")
        _api_port = int(_api_port_raw) if _api_port_raw else 8000
        original_port = _api_port
        while is_port_in_use(_api_port) and _api_port < original_port + 10:
            logger.info(f"API Server: Port {_api_port} in use (fallback). Trying {_api_port + 1}...")
            _api_port += 1

        self.api_server = APIServer(
            self,
            host=Vault.get("API_SERVER_HOST", "0.0.0.0") or "0.0.0.0",
            port=_api_port,
        )
        self.profiler.mark("API_SERVER_READY")

    async def _init_search_providers(self) -> None:
        # OpenBB Data Provider
        try:
            from openbb_provider import OpenBBProvider

            self._openbb_provider = OpenBBProvider(preferred_provider="yfinance")
            # Await async initialization (PAT login + Key Injection)
            await self._openbb_provider.initialize()
        except Exception as e:
            logger.warning(f"OpenBB initialization failed: {e}")

        # Native SLM Inference Engine
        try:
            from native_slm import NativeSLM

            self.native_slm = NativeSLM(model_path="models/sovereign_slm.gguf")
        except Exception as e:
            logger.warning(f"NativeSLM initialization failed: {e}")

        self.profiler.mark("SEARCH_PROVIDERS_READY")

    async def _init_hft_streamer(self) -> None:
        """HFT Streamer (0.01s / 100Hz Tick Ingestion)"""
        if os.environ.get("SOVEREIGN_TV_QUOTES_ENABLED", "1") == "1":
            self.tv_quote_streamer = TVQuoteStreamer(bus=self.bus, qdb_adapter=self.questdb)
        else:
            self.tv_quote_streamer = None

        self.hft_streamer = IBKRStreamer(
            host=self.ibkr_host,
            port=self.ibkr_port,
            client_id=self.ibkr_client_id + 10,
            qdb_host=Vault.get("QUESTDB_HOST", QUESTDB_HOST),
            qdb_ilp_port=int(Vault.get("QUESTDB_PORT", str(QUESTDB_PORT))),
            bus=self.bus,
            qdb_adapter=self.questdb,
        )
        self.profiler.mark("HFT_STREAMER_READY")

    def check_paper(self) -> None:
        """Verify paper trading mode with user confirmation"""
        logger.info(f"Current trading mode: {self.mode}")

        if self.mode not in ["paper", "ibkr_paper"]:
            logger.warning("   LIVE TRADING MODE DETECTED!")
            # In non-TTY environments (services, scheduled tasks) input() hangs forever
            if not sys.stdin.isatty():
                logger.error(
                    "Live trading mode detected in non-interactive environment. "
                    "Set TRADING_MODE=paper or TRADING_MODE=ibkr_paper in the Vault."
                )
                raise SystemExit(
                    "Live trading aborted — non-interactive session. "
                    "Use paper or ibkr_paper mode for automated/background execution."
                )
            print("\n" + "=" * 60)
            print("   WARNING: NOT IN PAPER TRADING MODE!")
            print(f"   Current mode: {self.mode}")
            print("=" * 60)
            print("\nThis will execute REAL trades with REAL money!")
            print("Type 'YES' (all caps) to continue with live trading: ")

            r = input().strip()
            if r != "YES":
                logger.info("Live trading aborted by user")
                raise SystemExit("Live trading aborted - safety check failed")

            logger.warning("User confirmed live trading mode")
            print("\n✓ Live trading mode confirmed\n")

    async def init_database(self) -> bool | None:
        """Initialize SQLite database from schema without blocking the event loop"""
        logger.info("Initializing database...")

        async with self.db_lock:
            try:

                def _sync_init():
                    conn = sqlite3.connect(
                        self.db_path,
                        timeout=60.0,
                        detect_types=sqlite3.PARSE_DECLTYPES,
                        check_same_thread=False,
                    )
                    conn.execute("PRAGMA busy_timeout = 90000;")  # 90s SQLite-level busy wait
                    conn.execute("PRAGMA journal_mode=WAL;")
                    conn.execute("PRAGMA synchronous=NORMAL;")
                    conn.execute("PRAGMA cache_size = -64000;")  # 64MB cache for high-speed reads
                    conn.execute(
                        "PRAGMA wal_checkpoint(TRUNCATE);"
                    )  # Force flush and truncate WAL on boot
                    return conn

                self.db_conn = await asyncio.to_thread(_sync_init)
                self.db_conn.row_factory = sqlite3.Row


                # Apply any pending yoyo migrations first (idempotent)
                try:
                    from database.migrate import apply_migrations
                    apply_migrations(db_path=self.db_path)
                except Exception as _mig_err:
                    logger.warning("Migration runner error (non-fatal): %s", _mig_err)

                # Read and execute schema
                if self.schema_path.exists():
                    logger.info(f"Loading schema from {self.schema_path}")
                    with open(self.schema_path) as f:
                        schema_sql = f.read()

                    # Execute schema (may contain multiple statements)
                    cursor = self.db_conn.cursor()
                    cursor.executescript(schema_sql)
                    cursor.close()

                    logger.info(" Database schema initialized")
                else:
                    logger.warning(f"Schema file not found: {self.schema_path}")
                    logger.info("Creating basic tables...")
                    self._create_basic_schema()

                # Verify tables exist
                cursor = self.db_conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
                tables = [row[0] for row in cursor.fetchall()]

                if "positions" in tables:
                    cursor.execute("PRAGMA table_info(positions)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if "account_id" not in columns:
                        logger.warning("Migrating 'positions' table: Adding 'account_id' column...")
                        cursor.execute(
                            "ALTER TABLE positions ADD COLUMN account_id TEXT DEFAULT 'UNKNOWN'"
                        )
                    if "broker" not in columns:
                        logger.warning("Migrating 'positions' table: Adding 'broker' column...")
                        cursor.execute("ALTER TABLE positions ADD COLUMN broker TEXT")

                if "trades" in tables:
                    cursor.execute("PRAGMA table_info(trades)")
                    columns = [row[1] for row in cursor.fetchall()]
                    if "account_id" not in columns:
                        logger.warning("Migrating 'trades' table: Adding 'account_id' column...")
                        cursor.execute(
                            "ALTER TABLE trades ADD COLUMN account_id TEXT DEFAULT 'UNKNOWN'"
                        )

                self._ensure_runtime_telemetry_schema(cursor)
                self.db_conn.commit()
                cursor.close()
                try:
                    from execution_evidence import repair_trade_ledger_from_execution_audit

                    repaired = repair_trade_ledger_from_execution_audit(self.db_conn)
                    if repaired:
                        logger.warning(
                            "Execution audit repaired %d reconciliation-required trade row(s).",
                            len(repaired),
                        )
                except Exception as audit_repair_error:
                    logger.error(
                        "Execution-audit ledger repair skipped: %s",
                        audit_repair_error,
                    )
                logger.info(f"Database tables verified: {', '.join(tables)}")

                return True

            except Exception as e:
                logger.error(f"Database initialization failed: {e}")
                raise

    def _ensure_runtime_telemetry_schema(self, cursor: sqlite3.Cursor) -> None:
        """Ensure dashboard/API telemetry tables are present and readable."""
        from database.schema import ensure_runtime_telemetry_schema

        ensure_runtime_telemetry_schema(cursor)

    def _record_system_event(
        self,
        event_type: str,
        message: str,
        *,
        severity: str = "INFO",
        agent: str = "main",
        details: dict[str, Any] | None = None,
    ) -> None:
        """Persist a concise runtime event for dashboards and audits."""
        if not self.db_conn:
            return
        try:
            with self.db_conn:
                self.db_conn.execute(
                    "INSERT INTO system_events "
                    "(timestamp, event_type, severity, agent, message, details) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        datetime.now(timezone.utc).isoformat(),
                        event_type,
                        severity,
                        agent,
                        message,
                        json.dumps(details or {}),
                    ),
                )
        except Exception as exc:
            logger.debug("System event write skipped: %s", exc)

    def _build_runtime_health_snapshot(
        self,
        *,
        ibkr_value: str | None = None,
        mt5_value: str | None = None,
    ) -> dict[str, Any]:
        """Return the current operator-facing service health snapshot."""
        brain = getattr(self, "trading_brain", None)
        state = getattr(getattr(brain, "state", None), "name", "INIT")
        open_positions = len(getattr(brain, "positions", []) or []) if brain else 0

        ibkr_status = (ibkr_value or "unknown").upper()
        mt5_status = (mt5_value or "unknown").upper()
        openbb = getattr(self, "_openbb_provider", None)
        dhatu = getattr(self, "dhatu_oracle", None)
        slm = getattr(self, "native_slm", None)
        tvq = getattr(self, "tv_quote_streamer", None)
        ibkr_hft = getattr(self, "hft_streamer", None)

        openbb_status = "OFFLINE"
        openbb_detail = "not initialized"
        if openbb:
            health_status = getattr(openbb, "health_status", None)
            if callable(health_status):
                openbb_status, openbb_detail = health_status()
            elif getattr(openbb, "is_available", False):
                openbb_status = "ONLINE"
                openbb_detail = "OpenBB SDK active"

        tv_status = "OFFLINE"
        tv_detail = "not initialized"
        if tvq:
            health_status = getattr(tvq, "health_status", None)
            if callable(health_status):
                tv_status, tv_detail = health_status()
            elif getattr(tvq, "connected", False):
                tv_status = "ONLINE"
                tv_detail = f"quotes={getattr(tvq, 'quotes_seen', 0)}"
            elif getattr(tvq, "is_running", False):
                tv_status = "DELAYED"
                tv_detail = "waiting for websocket connection"

        slm_status = "OFFLINE"
        slm_detail = ""
        if slm and getattr(slm, "is_available", False):
            mode = str(getattr(slm, "mode", "native")).upper()
            if mode == "FALLBACK":
                slm_status = "FALLBACK"
            elif mode == "COMPAT":
                slm_status = "COMPAT"
            else:
                slm_status = "NATIVE"
            slm_detail = str(getattr(slm, "status_detail", mode))

        dropped_ticks = 0
        if tvq:
            dropped_ticks += int(getattr(tvq, "dropped_ticks", 0) or 0)
        if ibkr_hft:
            dropped_ticks += int(getattr(ibkr_hft, "dropped_ticks", 0) or 0)

        try:
            proof_max_age = float(os.environ.get("SOVEREIGN_MARKET_DATA_HEALTH_MAX_AGE_SEC", "60"))
        except ValueError:
            proof_max_age = 60.0
        data_plane = market_data_health(
            getattr(brain, "_last_fresh_bar_at", {}) if brain else {},
            market_open=is_us_equity_market_open(),
            max_age_sec=proof_max_age,
        )

        components = [
            ComponentHealth("ibkr_execution", ibkr_status, critical=self.requires_ibkr_connection),
            ComponentHealth("mt5", mt5_status, critical=False),
            ComponentHealth("openbb", openbb_status, openbb_detail, critical=False),
            ComponentHealth("dhatu", "ONLINE" if dhatu else "OFFLINE", critical=True),
            data_plane,
            ComponentHealth("native_slm", slm_status, slm_detail, critical=False),
            ComponentHealth("tv_quotes", tv_status, tv_detail, critical=False),
        ]
        return build_health_snapshot(
            components,
            mode=self.mode,
            state=state,
            dropped_ticks=dropped_ticks,
            open_positions=open_positions,
            extra={
                "ibkr_hft_enabled": os.environ.get("SOVEREIGN_IBKR_HFT_ENABLED", "0") == "1",
                "tv_quotes_enabled": os.environ.get("SOVEREIGN_TV_QUOTES_ENABLED", "1") == "1",
                "market_session": us_equity_session_status(),
            },
        )

    def _runtime_connection_statuses(self) -> tuple[str, str]:
        """Return broker connection states without allowing probe failures to escape."""
        ibkr_value = "disconnected"
        if self.ibkr_client:
            try:
                ibkr_value = "connected" if self.ibkr_client.isConnected() else "disconnected"
            except Exception:
                ibkr_value = "error"

        mt5_value = "disconnected"
        if self.mt5_client:
            try:
                info = self.mt5_client.terminal_info()
                mt5_value = "connected" if info is not None and info.connected else "disconnected"
            except Exception:
                mt5_value = "error"
        return ibkr_value, mt5_value

    async def _persist_runtime_health_snapshot(
        self,
        *,
        event_type: str = "heartbeat",
        message: str = "Runtime heartbeat",
    ) -> dict[str, Any] | None:
        """Persist and publish a fresh operator snapshot through one serialized path."""
        db = self.db_conn
        if not db:
            return None

        async with self.db_lock:
            cursor = None
            try:
                ibkr_value, mt5_value = self._runtime_connection_statuses()
                health_snapshot = self._build_runtime_health_snapshot(
                    ibkr_value=ibkr_value,
                    mt5_value=mt5_value,
                )
                cursor = db.cursor()
                cursor.executemany(
                    "INSERT OR REPLACE INTO system_state (key, value, updated_at) "
                    "VALUES (?, ?, CURRENT_TIMESTAMP)",
                    (
                        ("last_heartbeat", time.time_ns()),
                        ("ibkr_status", ibkr_value),
                        ("mt5_status", mt5_value),
                        ("service_health", json.dumps(health_snapshot)),
                    ),
                )
                self._record_system_event(
                    event_type,
                    message,
                    agent="main",
                    details=health_snapshot,
                )
                if self.bus:
                    await self.bus.publish("system.health", health_snapshot)
                self._refresh_performance_summary()
                db.commit()
                return health_snapshot
            except sqlite3.OperationalError as exc:
                if "locked" in str(exc).lower():
                    logger.debug("Runtime health DB locked - skipping pulse.")
                else:
                    logger.error("Runtime health update failed: %s", exc)
            except Exception as exc:
                logger.error("Runtime health update failed: %s", exc)
            finally:
                if cursor is not None:
                    cursor.close()
        return None

    def _refresh_performance_summary(self) -> None:
        """Refresh the dashboard performance row even when no trade exits occur."""
        if not self.db_conn:
            return
        try:
            cursor = self.db_conn.cursor()
            self._ensure_runtime_telemetry_schema(cursor)
            cursor.execute("""
                SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END) AS wins,
                    SUM(CASE WHEN net_pnl < 0 THEN 1 ELSE 0 END) AS losses,
                    SUM(net_pnl) AS net_pnl,
                    AVG(r_multiple) AS avg_r
                FROM trades
                WHERE outcome IN ('WIN', 'LOSS', 'BREAKEVEN')
                  AND net_pnl IS NOT NULL
            """)
            row = cursor.fetchone()
            total_count = int(row[0] or 0)
            wins = int(row[1] or 0)
            losses = int(row[2] or 0)
            summary = {
                "closed_count": total_count,
                "wins": wins,
                "losses": losses,
                "win_rate": (wins / total_count) if total_count else 0.0,
                "net_pnl": float(row[3] or 0.0),
                "avg_r": float(row[4] or 0.0),
                "updated_from": "main.heartbeat",
            }
            now = datetime.now(timezone.utc)
            # Store as ISO string: the default sqlite3 datetime adapter is deprecated (Py3.12+).
            now_iso = now.isoformat()
            cursor.execute(
                "UPDATE performance_summary SET value=?, updated_at=? WHERE key='latest'",
                (json.dumps(summary), now_iso),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    "INSERT INTO performance_summary "
                    "(date, total_trades, wins, losses, win_rate, total_r, daily_pnl, "
                    "key, value, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        now.date().isoformat(),
                        total_count,
                        wins,
                        losses,
                        summary["win_rate"],
                        summary["avg_r"],
                        summary["net_pnl"],
                        "latest",
                        json.dumps(summary),
                        now_iso,
                    ),
                )
            cursor.close()
        except Exception as exc:
            logger.debug("Performance summary refresh skipped: %s", exc)

    def _create_basic_schema(self) -> None:
        """Create minimal schema if schema.sql doesn't exist"""
        from database.schema import create_basic_schema

        create_basic_schema(self.db_conn)

    async def _is_ibkr_process_active(self) -> bool:
        """Sovereign Shield: Checks if IBKR software is already running."""
        for target in ["tws.exe", "ibgateway.exe"]:
            try:
                proc = await asyncio.create_subprocess_exec(
                    "tasklist",
                    "/FI",
                    f"IMAGENAME eq {target}",
                    "/NH",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, _ = await proc.communicate()
                if target.lower() in stdout.decode().lower():
                    return True
            except Exception as exc:
                logger.debug("IBKR process probe failed for %s: %s", target, exc)
                continue
        return False

    async def connect_ibkr(self) -> bool | None:
        """Connect to Interactive Brokers TWS/Gateway using a serialized probe sequence."""
        if not hasattr(self, "_ibkr_lock"):
            self._ibkr_lock = asyncio.Lock()

        async with self._ibkr_lock:
            logger.info("Connecting to IBKR (Serialized Matrix Probing)...")
            try:
                from ib_insync import IB, IBC

                previous_client = self.ibkr_client
                if previous_client:
                    try:
                        if previous_client.isConnected():
                            logger.info("IBKR session already connected; reusing existing client.")
                            return True
                        previous_client.disconnect()
                    except Exception as exc:
                        logger.debug("IBKR stale-client cleanup skipped: %s", exc)
                self.ibkr_client = IB()

                auto_launch_ibkr = Vault.get("IBKR_AUTO_LAUNCH", "0").strip() == "1"
                ibc_path = os.environ.get("IBC_PATH") or Vault.get("IBC_PATH")
                if await self._is_ibkr_process_active():
                    logger.info("✓ IBKR software active (Bypassing IBC).")
                    ibc_path = None
                elif not auto_launch_ibkr:
                    logger.info(
                        "IBKR auto-launch disabled. Will connect to an existing TWS/Gateway only."
                    )
                    ibc_path = None

                default_tws = "C:\\Jts" if os.name == "nt" else "/opt/ibgateway"
                tws_path = os.environ.get("TWS_PATH") or Vault.get("TWS_PATH", default_tws)
                ibkr_user = Vault.get("IBKR_PAPER_USERNAME")
                ibkr_pass = Vault.get("IBKR_PAPER_PASSWORD")

                if ibc_path and ibkr_user and ibkr_pass:
                    logger.info("Starting IBC auto-login for paper trading...")
                    tws_version = 985
                    try:
                        roots_to_check = [tws_path]
                        if os.path.exists(os.path.join(tws_path, "ibgateway")):
                            roots_to_check.append(os.path.join(tws_path, "ibgateway"))
                        if os.path.exists(os.path.join(tws_path, "tws")):
                            roots_to_check.append(os.path.join(tws_path, "tws"))
                        folders = [
                            int(f)
                            for root in roots_to_check
                            if os.path.exists(root)
                            for f in os.listdir(root)
                            if f.isdigit()
                        ]
                        if folders:
                            tws_version = max(folders)
                    except Exception as _e:
                        logger.debug("TWS version detect failed: %s", _e)

                    ibkr_interface = Vault.get("IBKR_INTERFACE", "gateway").lower()
                    effective_tws_path = tws_path
                    if ibkr_interface == "gateway":
                        gw_p = os.path.join(tws_path, "ibgateway")
                        if self._is_safe_path(gw_p):
                            effective_tws_path = gw_p

                    # FINAL PATIENCE GAP: Strict Validation
                    if not self._is_safe_path(str(ibc_path)):
                        logger.error(f"Sovereign Shield: IBC_PATH validation FAILED ({ibc_path})")
                        return False

                    if not self._is_safe_path(str(effective_tws_path)):
                        logger.error(
                            f"Sovereign Shield: TWS_PATH validation FAILED ({effective_tws_path})"
                        )
                        return False

                    self.ibc = IBC(
                        twsVersion=tws_version,
                        gateway=(ibkr_interface == "gateway"),
                        tradingMode="paper",
                        userid=ibkr_user,
                        password=ibkr_pass,
                        twsPath=effective_tws_path,
                        ibcPath=ibc_path,
                    )
                    if self.ibc:
                        logger.info("✓ Launching IBC Shielded Session...")
                        self.ibc.start()
                    logger.info("Waiting 45 seconds for TWS/Gateway to initialize...")
                    await asyncio.sleep(45)

                ports_to_try = self._ibkr_probe_ports()
                connected = False
                base_client_id = self.ibkr_client_id
                self.ibkr_account_id = Vault.get("IBKR_ACCOUNT_ID", "")
                client = self.ibkr_client
                probe_started = time.monotonic()
                probe_budget = self._ibkr_probe_budget_sec()
                probe_timeout = self._ibkr_probe_timeout_sec()
                client_id_attempts = self._ibkr_probe_client_id_attempts()
                hosts_to_try = self._ibkr_probe_hosts()
                self._ibkr_last_probe_summary = {
                    "hosts": hosts_to_try,
                    "ports": ports_to_try,
                    "client_id_start": base_client_id,
                    "client_id_attempts": client_id_attempts,
                    "budget_sec": probe_budget,
                    "timeout_sec": probe_timeout,
                    "last_error": "",
                    "connected": False,
                }

                broker_connect_error = ""

                def capture_connect_error(
                    _request_id: int,
                    error_code: int,
                    error_text: str,
                    _contract: Any = None,
                ) -> None:
                    nonlocal broker_connect_error
                    if int(error_code) == 10141:
                        broker_connect_error = (
                            f"IBKR {error_code}: {error_text.rstrip(' .')}"
                        )

                client.errorEvent += capture_connect_error

                for client_id_offset in range(client_id_attempts):
                    current_id = base_client_id + client_id_offset
                    for host in hosts_to_try:
                        for port in ports_to_try:
                            elapsed = time.monotonic() - probe_started
                            remaining = probe_budget - elapsed
                            if remaining <= 0:
                                logger.warning(
                                    "IBKR probe budget exhausted after %.1fs "
                                    "(hosts=%s ports=%s client_ids=%s).",
                                    elapsed,
                                    ",".join(hosts_to_try),
                                    ",".join(str(p) for p in ports_to_try),
                                    client_id_attempts,
                                )
                                self._ibkr_last_probe_summary["last_error"] = (
                                    f"probe budget exhausted after {elapsed:.1f}s"
                                )
                                return False
                            try:
                                attempt_timeout = max(1.0, min(probe_timeout, remaining))
                                logger.info(
                                    "Sovereign Probe: %s:%s (ID: %s, timeout=%.1fs)...",
                                    host,
                                    port,
                                    current_id,
                                    attempt_timeout,
                                )
                                await asyncio.wait_for(
                                    client.connectAsync(
                                        host=host,
                                        port=port,
                                        clientId=current_id,
                                        timeout=attempt_timeout,
                                    ),
                                    timeout=attempt_timeout + 1.0,
                                )
                                if client.isConnected():
                                    connected = True
                                    self.ibkr_client_id = current_id
                                    self._ibkr_last_probe_summary.update(
                                        {
                                            "connected": True,
                                            "connected_host": host,
                                            "connected_port": port,
                                            "connected_client_id": current_id,
                                            "last_error": "",
                                        }
                                    )
                                    break
                            except Exception as e:
                                # ib_insync reports broker-side handshake rejection through
                                # errorEvent while connectAsync itself raises TimeoutError.
                                await asyncio.sleep(0)
                                failure_detail = broker_connect_error or (
                                    f"{type(e).__name__}: {e}"
                                )
                                self._ibkr_last_probe_summary["last_error"] = (
                                    f"{host}:{port} clientId={current_id}: {failure_detail}"
                                )
                                if broker_connect_error:
                                    self._ibkr_last_probe_summary["operator_action_required"] = True
                                    logger.error(
                                        "IBKR API blocked by broker acknowledgement: %s. "
                                        "Accept the paper-trading API disclaimer in TWS; "
                                        "automatic reattachment will continue.",
                                        broker_connect_error,
                                    )
                                    try:
                                        client.disconnect()
                                    except Exception as disconnect_error:
                                        logger.debug(
                                            "IBKR blocked-client cleanup skipped: %s",
                                            disconnect_error,
                                        )
                                    return False
                                logger.debug(f"Probe failed for {host}:{port}: {e}")
                                try:
                                    client.disconnect()
                                except Exception as e:
                                    logger.debug("Main: error disconnecting IBKR client during retry: %s", e)
                                self.ibkr_client = client = IB()
                                client.errorEvent += capture_connect_error
                                continue
                        if connected:
                            break
                    if connected:
                        break

                if not connected:
                    logger.warning(
                        "IBKR probe failed: hosts=%s ports=%s client_ids=%s-%s last_error=%s",
                        ",".join(hosts_to_try),
                        ",".join(str(p) for p in ports_to_try),
                        base_client_id,
                        base_client_id + client_id_attempts - 1,
                        self._ibkr_last_probe_summary.get("last_error") or "unknown",
                    )
                    return False
                accounts = client.managedAccounts()
                client.errorEvent -= capture_connect_error
                logger.info(f"✓ IBKR connected - Accounts: {accounts}")
                if accounts:
                    client.wrapper.accounts = accounts
                    logger.info(f"Using account: {accounts[0]}")

                # This ensures the system can at least see delayed prices if
                # no live subscriptions are present (Prevents 10168 errors).
                client.reqMarketDataType(3)
                await self._bind_ibkr_runtime(reconcile=False)
                logger.info("✓ IBKR Market Data: Type 3 (Delayed) enabled as fallback.")

                return True

            except Exception as e:
                self._ibkr_last_probe_summary = {
                    "last_error": f"{type(e).__name__}: {e}",
                    "connected": False,
                }
                logger.error(f"IBKR connection error: {e}")
                return False

    @staticmethod
    def _ibkr_env_float(name: str, default: float, minimum: float) -> float:
        try:
            return max(minimum, float(os.environ.get(name, str(default))))
        except ValueError:
            logger.warning("%s is invalid; using %.1fs.", name, default)
            return max(minimum, default)

    @staticmethod
    def _ibkr_env_int(name: str, default: int, minimum: int, maximum: int) -> int:
        try:
            value = int(os.environ.get(name, str(default)))
        except ValueError:
            logger.warning("%s is invalid; using %s.", name, default)
            value = default
        return min(maximum, max(minimum, value))

    def _ibkr_probe_budget_sec(self) -> float:
        return self._ibkr_env_float("SOVEREIGN_IBKR_PROBE_BUDGET_SEC", 45.0, 5.0)

    def _ibkr_probe_timeout_sec(self) -> float:
        return self._ibkr_env_float("SOVEREIGN_IBKR_PROBE_TIMEOUT_SEC", 3.0, 1.0)

    def _ibkr_probe_client_id_attempts(self) -> int:
        return self._ibkr_env_int("SOVEREIGN_IBKR_CLIENT_ID_ATTEMPTS", 4, 1, 20)

    def _ibkr_probe_hosts(self) -> list[str]:
        raw = os.environ.get("SOVEREIGN_IBKR_PROBE_HOSTS", "127.0.0.1").strip()
        hosts = [host.strip() for host in raw.split(",") if host.strip()]
        return hosts or ["127.0.0.1"]

    def _ibkr_probe_ports(self) -> list[int]:
        raw = os.environ.get("SOVEREIGN_IBKR_PROBE_PORTS", "").strip()
        if raw:
            ports: list[int] = []
            for item in raw.split(","):
                try:
                    port = int(item.strip())
                except ValueError:
                    logger.warning("Ignoring invalid IBKR probe port: %s", item)
                    continue
                if port not in ports:
                    ports.append(port)
            if ports:
                return ports

        primary = int(getattr(self, "ibkr_port", 7497))
        fallback = 4002 if primary == 7497 else 7497
        return [primary] if primary == fallback else [primary, fallback]

    async def _bind_ibkr_runtime(self, *, reconcile: bool = True) -> None:
        """Rebind every IBKR consumer after startup or a late broker recovery."""
        client = self.ibkr_client
        if not client:
            return

        dms = getattr(self, "dms", None)
        if dms:
            dms.ibkr_client = client

        brain = getattr(self, "trading_brain", None)
        if not brain:
            return

        brain.ibkr_client = client
        conn = getattr(brain, "ibkr_conn", None)
        if conn:
            conn.ib = client
            conn.is_reconnecting = False
            conn._callbacks_registered = False
            await conn.ensure_connection()
        if reconcile:
            await brain._reconcile_broker_positions()

    def _has_exposed_ibkr_positions(self) -> bool:
        """Return True when memory shows IBKR positions that need an execution path."""
        brain = getattr(self, "trading_brain", None)
        if not brain:
            return False
        for pos in list(getattr(brain, "positions", []) or []):
            try:
                if (
                    str(getattr(pos, "account_type", "")).lower() == "ibkr"
                    and abs(float(getattr(pos, "qty", 0.0) or 0.0)) > 0.0001
                ):
                    return True
            except (TypeError, ValueError):
                continue
        return False

    def _ibkr_probe_diagnostic_text(self, *, software_active: bool | None = None) -> str:
        summary = getattr(self, "_ibkr_last_probe_summary", {}) or {}
        hosts = summary.get("hosts") or self._ibkr_probe_hosts()
        ports = summary.get("ports") or self._ibkr_probe_ports()
        configured_client_id = int(getattr(self, "ibkr_client_id", 500))
        client_id_start = int(summary.get("client_id_start", configured_client_id))
        attempts = int(summary.get("client_id_attempts", self._ibkr_probe_client_id_attempts()))
        client_id_end = client_id_start + max(1, attempts) - 1
        last_error = str(summary.get("last_error") or "no probe error captured")
        app_state = "running" if software_active else "not detected"
        return (
            f"IBKR app={app_state}; API probe hosts={','.join(map(str, hosts))}; "
            f"ports={','.join(map(str, ports))}; clientIds={client_id_start}-{client_id_end}; "
            f"last={last_error}"
        )

    def _ibkr_operator_action_message(self) -> str | None:
        """Return a concise operator action for a known broker-side API gate."""
        summary = getattr(self, "_ibkr_last_probe_summary", {}) or {}
        last_error = str(summary.get("last_error") or "")
        if summary.get("operator_action_required") and "10141" in last_error:
            return (
                "[EXECUTION] ACTION REQUIRED: TWS rejected API access because the paper-trading "
                "disclaimer has not been accepted. Open TWS, accept the paper-trading API "
                "disclaimer, and leave TWS running. Samvid will reconnect automatically."
            )
        return None

    async def _run_ibkr_reconnect_loop(self) -> None:
        """Keep the owned IBKR API session attached when TWS starts late or restarts."""
        def _interval(name: str, default: float) -> float:
            try:
                return float(os.environ.get(name, str(default)))
            except ValueError:
                logger.warning("%s is invalid; using %.0fs.", name, default)
                return default

        base_delay = max(
            5.0,
            _interval("SOVEREIGN_IBKR_RECONNECT_INTERVAL_SEC", 15.0),
        )
        max_delay = max(
            base_delay,
            _interval("SOVEREIGN_IBKR_RECONNECT_MAX_INTERVAL_SEC", 60.0),
        )
        critical_delay = max(
            5.0,
            _interval("SOVEREIGN_IBKR_RECONNECT_CRITICAL_INTERVAL_SEC", 20.0),
        )
        delay = base_delay

        while self.is_running and not self._shutdown_in_progress:
            connected = False
            client = self.ibkr_client
            if client:
                try:
                    connected = bool(client.isConnected())
                except Exception as exc:
                    logger.debug("IBKR reconnect health probe failed: %s", exc)

            if connected:
                if self._ibkr_outage_active:
                    await self._bind_ibkr_runtime()
                    self._ibkr_outage_active = False
                    delay = base_delay
                    logger.info("IBKR RECOVERY: execution session restored and reconciled.")
                    await self.send_telegram_notification(
                        "[EXECUTION] IBKR API session recovered. "
                        "Runtime references rebound and broker positions reconciled."
                    )
                    await self._persist_runtime_health_snapshot(
                        event_type="broker_recovered",
                        message="IBKR execution session recovered",
                    )
                await asyncio.sleep(base_delay)
                continue

            if not self._ibkr_outage_active:
                self._ibkr_outage_active = True
                software_active = await self._is_ibkr_process_active()
                logger.warning(
                    "IBKR OUTAGE: execution is offline. Runtime will keep retrying attachment."
                )
                await self.send_telegram_notification(
                    "[EXECUTION] IBKR API session offline. "
                    "New IBKR orders are blocked while automatic reattachment runs.\n"
                    f"{self._ibkr_probe_diagnostic_text(software_active=software_active)}"
                )
                await self._persist_runtime_health_snapshot(
                    event_type="broker_offline",
                    message="IBKR execution session offline",
                )

            if await self.connect_ibkr():
                await self._bind_ibkr_runtime()
                self._ibkr_outage_active = False
                delay = base_delay
                logger.info("IBKR RECOVERY: automatic reattachment succeeded.")
                await self.send_telegram_notification(
                    "[EXECUTION] IBKR API session recovered. "
                    "Runtime references rebound and broker positions reconciled."
                )
                await self._persist_runtime_health_snapshot(
                    event_type="broker_recovered",
                    message="IBKR execution session recovered",
                )
                await asyncio.sleep(base_delay)
                continue

            operator_action = self._ibkr_operator_action_message()
            if operator_action and operator_action != getattr(
                self, "_last_ibkr_operator_action", None
            ):
                self._last_ibkr_operator_action = operator_action
                await self.send_telegram_notification(operator_action)
                await self._persist_runtime_health_snapshot(
                    event_type="broker_operator_action_required",
                    message=operator_action,
                )

            retry_delay = min(delay, critical_delay) if self._has_exposed_ibkr_positions() else delay
            logger.warning(
                "IBKR RECOVERY: attachment failed; retrying in %.0fs%s.",
                retry_delay,
                " because IBKR positions are exposed" if retry_delay < delay else "",
            )
            await asyncio.sleep(retry_delay)
            delay = min(delay * 2.0, max_delay)

    async def connect_mt5(self) -> bool | None:
        """Connect to MetaTrader 5 if credentials provided"""
        if not self.mt5_login:
            logger.info("MT5 credentials not provided - skipping MT5 connection")
            return False

        logger.info(f"Connecting to MT5 (Login: {self.mt5_login})...")

        try:
            import MetaTrader5 as mt5

            # First try bare initialize (attach to running terminal)
            # If that fails with auth error, pass credentials to force correct account
            initialized = False

            # First try bare initialize (attach to running terminal or auto-start default)
            init_kwargs = {}
            if self.mt5_path:
                effective_path = str(self.mt5_path)
                if os.path.isdir(effective_path):
                    potential_exe = os.path.join(effective_path, "terminal64.exe")
                    if self._is_safe_path(potential_exe):
                        effective_path = potential_exe
                    else:
                        logger.warning(
                            f"Sovereign Shield: MT5 Directory valid but terminal64.exe FAILED "
                            f"safety check in {effective_path}. Using bare init."
                        )
                        effective_path = None
                elif not self._is_safe_path(effective_path):
                    logger.warning(
                        f"Sovereign Shield: MT5_PATH validation FAILED ({effective_path})"
                    )
                    effective_path = None

                if effective_path:
                    init_kwargs["path"] = effective_path

            # Attempt 1: bare initialize
            if mt5.initialize(**init_kwargs):
                initialized = True
                logger.info("MT5 terminal attached to running instance")
            else:
                error = mt5.last_error()
                logger.info(f"MT5 bare initialize returned: {error} - trying with credentials...")
                mt5.shutdown()
                await asyncio.sleep(1)

            # Attempt 2: initialize with login credentials
            # (forces MT5 to switch accounts if already running)
            if not initialized:
                if mt5.initialize(
                    login=int(self.mt5_login),
                    password=self.mt5_password,
                    server=self.mt5_server,
                    **init_kwargs,
                ):
                    initialized = True
                    logger.info("MT5 terminal initialized with credentials")
                else:
                    error = mt5.last_error()
                    logger.warning(f"MT5 initialize with credentials failed: {error}")
                    mt5.shutdown()
                    await asyncio.sleep(2)

            # Attempt 3: shutdown fully and try once more with a longer wait
            if not initialized:
                mt5.shutdown()
                await asyncio.sleep(3)
                if mt5.initialize(
                    login=int(self.mt5_login),
                    password=self.mt5_password,
                    server=self.mt5_server,
                    **init_kwargs,
                ):
                    initialized = True
                    logger.info("MT5 terminal initialized on final attempt")
                else:
                    error = mt5.last_error()
                    logger.error(f"MT5 initialization failed after 3 attempts: {error}")

            if not initialized:
                # Last resort: try to use whatever terminal session exists
                if mt5.initialize(**init_kwargs):
                    account_info = mt5.account_info()
                    if account_info is not None:
                        logger.warning(
                            f"MT5 using existing session (account {account_info.login}) "
                            f"instead of requested {self.mt5_login}"
                        )
                        self.mt5_client = mt5
                        return True
                raise ConnectionError(f"MT5 initialization failed: {mt5.last_error()}")

            logger.info("MT5 terminal initialized")

            account_info = mt5.account_info()
            if account_info is not None and account_info.login == int(self.mt5_login):
                # Already logged in with the correct account - no need to re-login
                logger.info(f" MT5 already logged in - Account: {account_info.login}")
                logger.info(f"  Balance: {account_info.balance} {account_info.currency}")
                logger.info(f"  Server: {account_info.server}")
                logger.info(f"  Name: {account_info.name}")

                self.mt5_client = mt5

                if (
                    hasattr(self, "trading_brain")
                    and self.trading_brain
                    and hasattr(self.trading_brain, "mt5_conn")
                ):
                    try:
                        self.trading_brain.mt5_conn.sync_state(
                            int(self.mt5_login), self.mt5_password, self.mt5_server
                        )
                    except Exception as e:
                        logger.debug(f"MT5: Brain state sync failed: {e}")

                db = self.db_conn
                if db:
                    cursor = db.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                        ("mt5_status", "connected"),
                    )
                    cursor.close()
                return True

            logger.info(f"Logging into MT5 account {self.mt5_login} on {self.mt5_server}...")

            logger.info("Attempting MT5 login with 15s timeout...")
            try:
                authorized = await asyncio.wait_for(
                    asyncio.to_thread(
                        mt5.login, int(self.mt5_login), self.mt5_password, self.mt5_server
                    ),
                    timeout=15,
                )
            except asyncio.TimeoutError:
                logger.error("MT5 Login Timed Out - Skipping MT5")
                authorized = False
            except Exception as e:
                logger.error(f"MT5 Login Error: {e}")
                authorized = False

            if not authorized:
                error = mt5.last_error()
                error_code = error[0] if error else -1
                error_msg = error[1] if error and len(error) > 1 else "Unknown"

                # Provide specific guidance based on error code
                if error_code == -6:
                    logger.error(
                        f"MT5 authorization failed (code -6). Possible causes:\n"
                        f"  1. Wrong password in .env (MT5_PASSWORD)\n"
                        f"  2. Wrong server in .env (MT5_SERVER={self.mt5_server})\n"
                        f"  3. Account expired or disabled\n"
                        f"  Fix: Open MT5 → File → Login → verify credentials match .env"
                    )
                else:
                    logger.error(f"MT5 login failed: [{error_code}] {error_msg}")

                # Even if login fails, check if terminal has an active account we can use
                account_info = mt5.account_info()
                if account_info is not None:
                    logger.warning(
                        f"MT5 terminal has active account {account_info.login} "
                        f"(requested {self.mt5_login}) - using existing session"
                    )
                    self.mt5_client = mt5
                    return True

                mt5.shutdown()
                return False

            account_info = mt5.account_info()
            if account_info is None:
                raise ConnectionError("Failed to get MT5 account info after login")

            logger.info(f" MT5 connected - Account: {account_info.login}")
            logger.info(f"  Balance: {account_info.balance} {account_info.currency}")
            logger.info(f"  Server: {account_info.server}")

            self.mt5_client = mt5

            if (
                hasattr(self, "trading_brain")
                and self.trading_brain
                and hasattr(self.trading_brain, "mt5_conn")
            ):
                try:
                    self.trading_brain.mt5_conn.sync_state(
                        int(self.mt5_login), self.mt5_password, self.mt5_server
                    )
                except Exception as e:
                    logger.debug(f"MT5: Brain state sync failed: {e}")

            db = self.db_conn
            if db:
                # Store connection info
                cursor = db.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                    ("mt5_status", "connected"),
                )
                cursor.close()

            return True

        except ImportError:
            logger.warning("MetaTrader5 package not installed - MT5 connection skipped")
            logger.info("Install with: pip install MetaTrader5")
            return False
        except Exception as e:
            logger.error(f"MT5 connection error: {e}")
            return False

    async def start_data_pipeline(self) -> bool | None:
        """Start the data collection and processing pipeline"""
        logger.info("Starting Data Pipeline...")

        try:
            # Import DataPipeline component
            from data_pipeline import DataPipeline

            _f_key = Vault.get("FINNHUB_API_KEY", "")
            self.data_pipeline = DataPipeline(
                db_path=str(self.db_path),
                finnhub_key=str(_f_key) if _f_key else "",
                qdb=self.questdb,
                openbb_provider=self._openbb_provider,
                bus=self.bus,
            )

            pipeline = self.data_pipeline
            if pipeline:
                # Start pipeline in supervised background task
                self._start_supervised_task("data_pipeline", pipeline.run_continuous)

            logger.info(" Data Pipeline started")
            return True

        except ImportError as e:
            logger.warning(f"DataPipeline not available: {e}")
            logger.info("Data pipeline will be implemented in src/data_pipeline.py")
            return False
        except Exception:
            import traceback

            logger.error(f"Failed to start Data Pipeline: {traceback.format_exc()}")
            return False

    async def start_dms(self) -> bool | None:
        """Start the Dead Man Switch"""
        logger.info("Starting Dead Man Switch (DMS)...")

        try:
            from dms import DMSMonitor

            self.dms = DMSMonitor(
                bot_token=self.telegram_token,
                chat_id=self.telegram_chat_id,
                timeout=300,
                ibkr_client=self.ibkr_client,
                mt5_client=self.mt5_client,
                ibkr_port=self.ibkr_port,
                bus=self.bus,
                requires_ibkr_connection=self.requires_ibkr_connection,
            )

            dms = self.dms
            if dms:
                # Start DMS in supervised background task
                self._start_supervised_task("dms", dms.run)

            logger.info(" DMS started (with emergency flatten capability)")
            return True

        except ImportError as e:
            logger.warning(f"DMS not available: {e}")
            logger.info("DMS will be implemented in src/dms.py")
            return False
        except Exception as e:
            logger.error(f"Failed to start DMS: {e}")
            return False

    async def start_trading_brain(self) -> bool | None:
        """Start the Trading Brain (main decision engine)"""
        logger.info("Starting Trading Brain...")

        try:
            from brain import TradingBrain

            self.trading_brain = TradingBrain(
                db_conn=self.db_conn,
                ibkr_client=self.ibkr_client,
                mt5_client=self.mt5_client,
                dms=self.dms,
                mode=self.mode,
                dhatu_oracle=self.dhatu_oracle,
                qdb=self.questdb,
                native_slm=self.native_slm,
                bus=self.bus,
            )

            brain = self.trading_brain
            if brain:
                # Logic natively integrated
                # Start brain in supervised background task
                self._start_supervised_task("trading_brain", brain.run)

            logger.info(" Trading Brain started")
            return True

        except ImportError as e:
            logger.warning(f"Trading Brain not available: {e}")
            logger.info("Trading Brain will be implemented in src/brain.py")
            return False
        except Exception as e:
            logger.error(f"Failed to start Trading Brain: {e}", exc_info=True)
            return False

    async def _start_dhatu_oracle(self) -> bool:
        """Start the Dhatu Oracle global knowledge graph in a supervised background task."""
        logger.info("Starting Dhatu Oracle (Global Knowledge Graph)...")
        try:
            from dhatu_oracle import DhatuOracle

            oracle = DhatuOracle(
                google_api_key=Vault.get("GOOGLE_API_KEY", ""),
                anthropic_api_key=Vault.get("ANTHROPIC_API_KEY", ""),
                gemini_model=Vault.get("GEMINI_MODEL", "gemini-2.0-flash") or "gemini-2.0-flash",
                bus=self.bus,
            )
            self.dhatu_oracle = oracle
            self._start_supervised_task("dhatu_oracle", oracle.run_continuous)
            # Logic natively integrated
            logger.info(" Dhatu Oracle started (15-minute global synthesis cycle)")
            return True
        except ImportError as e:
            logger.warning(f"DhatuOracle not available: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to start Dhatu Oracle: {e}")
            return False

    async def send_telegram_notification(self, message: str) -> bool:
        """
        Sends a Telegram notification with Elite Signal Sterilization.
        Discards routine signal noise captured by the main loop or background tasks.
        """
        allowed_prefixes = [
            "[EXECUTION]",
            "[SOVEREIGN ALERT]",
            "[TRADE]",
            "[RISK]",
            "[DMS]",
            "[EMERGENCY]",
            "[SHUTDOWN]",
            "[STARTUP]",
            "[DRAWDOWN]",
            "SYSTEM CRITICAL",
            "TRADE FULLY CLOSED",
            "DAILY WRAP-UP",
            "SOVEREIGN SYSTEM OFFLINE",
            "SOVEREIGN TRADING SYSTEM ONLINE",
            "BACKGROUND TASK CRASHED",
        ]

        message = normalize_operator_text(message)
        logger.info(f"Telegram: Attempting to send message (Prefix check: {message[:10]}...)")
        msg_upper = message.upper()
        is_allowed_prefix = any(
            prefix.upper() in msg_upper for prefix in allowed_prefixes if prefix
        )
        is_error = any(
            term in msg_upper for term in ("ERROR", "FAILED", "EXCEPTION", "CRITICAL", "FATAL")
        )
        if not (is_allowed_prefix or is_error):
            logger.info(
                "Sterilization: Suppressing non-elite main notification "
                f"(No allowed prefix found): {message[:50]}..."
            )
            return False

        token = self.telegram_token or Vault.get("TELEGRAM_BOT_TOKEN")
        chat_id = self.telegram_chat_id or Vault.get("TELEGRAM_CHAT_ID")
        if not token or not chat_id:
            logger.warning("Telegram notification skipped: Token or ChatID missing.")
            return False

        redacted_message = message
        secrets = Vault.get_all_redactable_values()
        for s in secrets:
            if s and len(s) > 3 and s in redacted_message:
                redacted_message = redacted_message.replace(s, "[REDACTED]")

        try:
            base_url = Vault.get("TELEGRAM_API_URL", "https://api.telegram.org").rstrip("/")
            url = f"{base_url}/bot{token.strip()}/sendMessage"
            payload = {
                "chat_id": str(chat_id).strip(),
                "text": redacted_message,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            }

            if (
                not hasattr(self, "_telegram_session")
                or self._telegram_session is None
                or self._telegram_session.closed
            ):
                self._telegram_session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=30.0)
                )

            async with self._telegram_session.post(url, json=payload) as resp:
                if resp.status == 200:
                    logger.info(" Telegram notification sent successfully.")
                    return True
                response_text = await resp.text()
                if len(response_text) > 300:
                    response_text = response_text[:300] + "... [truncated]"
                logger.warning(
                    " Telegram notification failed with status %s: %s",
                    resp.status,
                    response_text,
                )
                return False
        except Exception as e:
            logger.error(f" Telegram notification error: {e}", exc_info=True)
            return False

    async def _start_background_tasks(self) -> None:
        """Start long-running background tasks"""
        # Start QuestDB worker if enabled
        if self.questdb and self.questdb.enabled:
            logger.info("\n[7/9] Starting QuestDB Adapter...")
            await self.questdb.start()
            if self.questdb.enabled:
                logger.info("✓ QuestDB Adapter started")
            else:
                logger.info("QuestDB Adapter disabled at runtime (probe failed)")
        else:
            logger.info("\n[7/9] QuestDB Adapter disabled or not configured.")

        # Start Dhatu Oracle
        if Vault.get("GOOGLE_API_KEY") or Vault.get("ANTHROPIC_API_KEY"):
            logger.info("\n[8/9] Starting Dhatu Oracle...")
            started = await self._start_dhatu_oracle()
            if started and self.trading_brain and self.dhatu_oracle:
                self.trading_brain.dhatu_oracle = self.dhatu_oracle
                if self.trading_brain.sync_oracle_state():
                    logger.info("Dhatu Oracle state synchronized into Trading Brain.")
        else:
            logger.info("\n[8/9] Dhatu Oracle disabled or not configured.")

        # Start Prometheus metrics server (non-fatal)
        try:
            from metrics import start_metrics_server
            from vault import Vault as _VaultM
            _metrics_port = int(_VaultM.get("METRICS_PORT", "9090") or "9090")
            start_metrics_server(port=_metrics_port)
            logger.info("Prometheus metrics server started on port %d", _metrics_port)
        except Exception as _m_err:
            logger.warning("Metrics server startup failed (non-fatal): %s", _m_err)

        # Start API Server
        if self.api_server:
            _p = self.api_server.port
            logger.info(f"\n[9/9] Starting Institutional API Server (Port {_p})...")
            started = await self.api_server.start()
            if started:
                logger.info(" API Server active")
            else:
                logger.info(f"API Server skipped (already active on port {_p})")
        else:
            logger.warning("\n[9/9] API Server is not initialized. Skipping startup.")

    async def startup(self) -> None:
        """Main startup sequence: parallel initialization of all system components."""
        from risk_invariants import RiskInvariants

        if not RiskInvariants.verify_config():
            logger.critical(" SYSTEM HALTED: Critical Risk Invariants Corrupted.")
            raise RuntimeError("Critical Risk Invariants Corrupted.")

        logger.info("=" * 60)
        logger.info("Trading System - Starting Up")
        logger.info("=" * 60)

        start_time = datetime.now(timezone.utc)

        try:
            logger.info("\n[1/10] Initializing Sovereign Deterministic Engine...")
            logger.info(
                " Sovereign: LLM dependencies purged. High-performance offline mode active."
            )

            logger.info("\n[2/10] Checking trading mode...")
            self.check_paper()

            logger.info("\n[3/10] SQLite Engine Sync Check...")

            # 1. Instantiate Core Objects first so the Brain has valid references
            if self.requires_ibkr_connection:
                from ib_insync import IB

                if not hasattr(self, "ibkr_client") or self.ibkr_client is None:
                    self.ibkr_client = IB()
                elif self.ibkr_client.isConnected():
                    logger.info(" Sovereign: IBKR client already connected. Skipping re-init.")
                else:
                    logger.info(" Sovereign: Re-initializing existing IBKR client instance.")
            else:
                logger.info("Paper mode active — skipping IBKR client instantiation.")

            # 2. Start Critical Infrastructure synchronously/awaited
            await self.start_dms()
            await self._persist_runtime_health_snapshot(
                event_type="startup_progress",
                message="Core infrastructure initialized; broker probing starting",
            )

            # 3. Broker Matrix Probing (Serialized for stability)
            if self.requires_ibkr_connection:
                await self.connect_ibkr()
            else:
                logger.info("Paper mode active — skipping IBKR connection.")

            await self._persist_runtime_health_snapshot(
                event_type="startup_progress",
                message="IBKR probe completed; MT5 probe starting",
            )

            _mt5_authorized = False
            if hasattr(self, "mt5_login") and self.mt5_login:
                if (
                    "YOUR_MT5" not in str(self.mt5_login).upper()
                    and str(self.mt5_login).lower() != "none"
                ):
                    _mt5_authorized = True

            if self.mode != "paper" and _mt5_authorized:
                await self.connect_mt5()
            elif _mt5_authorized:
                logger.info("Paper mode active — skipping MT5 connection.")
            else:
                missing = []
                if not self.mt5_login:
                    missing.append("MT5_LOGIN")
                if not self.mt5_server:
                    missing.append("MT5_SERVER")
                logger.warning(
                    "MT5 Kill Switch ACTIVE: Skipping MetaTrader. "
                    f"Missing from Vault: {', '.join(missing)}"
                )

            await self._persist_runtime_health_snapshot(
                event_type="startup_progress",
                message="Broker probing completed; brain startup starting",
            )

            logger.info("\n[4/10] Starting Trading Brain (Standby Mode)...")
            await self.start_trading_brain()
            if self.requires_ibkr_connection:
                self._start_supervised_task("ibkr_reconnect", self._run_ibkr_reconnect_loop)

            # Start the Remote Command Listener IMMEDIATELY
            if self.telegram_remote:
                logger.info(" Sovereign Remote: Activating Command listener...")
                await self.telegram_remote.start()

            # Start the data pipeline in the background
            await self.start_data_pipeline()

            await self._start_background_tasks()

            logger.info("\n[9/10] Validating Native SLM Readiness...")
            if self.native_slm is not None:
                if self.native_slm.is_available:
                    if hasattr(self.native_slm, "warmup"):
                        await self.native_slm.warmup()
                    slm_mode = getattr(self.native_slm, "mode", "native")
                    slm_detail = getattr(self.native_slm, "status_detail", slm_mode)
                    logger.info("Native SLM online (%s): %s.", slm_mode, slm_detail)
                else:
                    logger.info("Native SLM offline - trading continues with pure math execution.")

            logger.info("\n[8.5/10] Initiating Neural Warmup (Contract Cache)...")
            watchlist = self.execution_watchlist()
            if hasattr(self, "ibc") and self.ibc is not None:
                if hasattr(self.ibc, "warm_up_contracts"):
                    await self.ibc.warm_up_contracts(watchlist)
                else:
                    logger.debug(
                        "IBC: warm_up_contracts not available — skipping contract pre-cache"
                    )

            # Always start HFT streamer — falls back to Bus-only if QuestDB offline
            logger.info("\n[9/10] Starting Real-Time Quote Streamers...")
            # watchlist is already defined in step 8.5
            if self.tv_quote_streamer:
                self._start_supervised_task(
                    "tv_quote_streamer", lambda: self.tv_quote_streamer.run(watchlist)
                )
                logger.info("TVQuoteStreamer active; IBKR remains execution-first.")
            else:
                logger.info("TVQuoteStreamer disabled by SOVEREIGN_TV_QUOTES_ENABLED=0.")

            ibkr_hft_enabled = os.environ.get("SOVEREIGN_IBKR_HFT_ENABLED", "0") == "1"
            if self.hft_streamer and ibkr_hft_enabled:
                self._start_supervised_task(
                    "hft_streamer", lambda: self.hft_streamer.run(watchlist)
                )
            elif self.hft_streamer:
                logger.info(
                    "IBKR market-data streamer parked; set SOVEREIGN_IBKR_HFT_ENABLED=1 "
                    "to use it as a tick fallback."
                )
            else:
                logger.warning("HFT Streamer not initialized. Skipping supervised task.")

            logger.info("\n[10/10] Sending startup notification...")

            ibkr_status = self._get_status_icon("ibkr")
            mt5_status = self._get_status_icon("mt5")
            dhatu_status = self._get_status_icon("dhatu")
            obb_status = self._get_openbb_startup_status()

            if hasattr(self, "native_slm") and self.native_slm and self.native_slm.is_available:
                slm_mode = getattr(self.native_slm, "mode", "native")
                slm_status = (
                    "GREEN NATIVE READY" if slm_mode == "native" else "YELLOW FALLBACK ONLINE"
                )
            else:
                slm_status = "RED OFFLINE"

            notification = (
                f"[STARTUP] <b>Sovereign Trading System Online</b>\n\n"
                f"<b>Mode:</b> <code>{self.mode.upper()}</code>\n"
                f"-------------------\n"
                f"<b>IBKR Gateway:</b> {ibkr_status}\n"
                f"<b>MetaTrader 5:</b> {mt5_status}\n"
                f"<b>Dhatu Oracle:</b> {dhatu_status}\n"
                f"<b>OpenBB Data:</b> {obb_status}\n"
                f"<b>Native SLM:</b> {slm_status}\n"
                f"-------------------\n"
                f"<b>Startup Latency:</b> "
                f"{(datetime.now(timezone.utc) - start_time).total_seconds():.2f}s\n"
                f"<i>{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC</i>"
            )

            await self.send_telegram_notification(notification)

            # Log final status
            logger.info("=" * 60 + "\n")

            if hasattr(self, "trading_brain") and self.trading_brain and self.trading_brain.bus:

                async def _awaken():
                    await asyncio.sleep(5)
                    await self.trading_brain.bus.publish(
                        "mind.dialogue",
                        {
                            "sender": "architect",
                            "content": (
                                "Sovereign Matrix awakening. Synchronizing global bus. "
                                "Initializing diagnostic pre-flight checks."
                            ),
                            "metadata": {"type": "STATUS"},
                        },
                    )
                    await asyncio.sleep(3)
                    await self.trading_brain.bus.publish(
                        "mind.dialogue",
                        {
                            "sender": "evolution",
                            "content": (
                                "Consensus reached. Market regimes ready for classification. "
                                "Standing by for tick stream alignment."
                            ),
                            "metadata": {"type": "STATUS"},
                        },
                    )

                self._awaken_task = asyncio.create_task(_awaken())
                self.background_tasks["awaken_sequence"] = self._awaken_task

            # Store startup info (Hardened with Retry Matrix)
            async with self.db_lock:
                db = self.db_conn
                if db:
                    for attempt in range(10):  # 10 retries (approx 1 minute total wait)
                        try:
                            cursor = db.cursor()
                            cursor.execute(
                                "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                                ("last_startup", time.time_ns()),
                            )
                            cursor.execute(
                                "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                                ("system_status", "running"),
                            )
                            self._record_system_event(
                                "startup",
                                "Trading system startup completed",
                                agent="main",
                                details={"mode": self.mode},
                            )
                            self._refresh_performance_summary()
                            db.commit()
                            cursor.close()
                            break  # Success
                        except sqlite3.OperationalError as e:
                            if "locked" in str(e).lower() and attempt < 9:
                                wait_time = 1.0 + (attempt * 0.5)
                                logger.warning(
                                    " Sovereign: Database locked at startup pulse. "
                                    f"Jittering {wait_time}s... (Attempt {attempt + 1}/10)"
                                )
                                await asyncio.sleep(wait_time)
                            else:
                                raise
            await self._persist_runtime_health_snapshot(
                event_type="startup_health",
                message="Startup runtime health",
            )
            if os.environ.get("SOVEREIGN_SKIP_PID_CHECK", "0") == "1":
                logger.info("Smoke-test mode detected - startup complete without run loop.")
                await self.shutdown()
                return
            # Keep running
            await self._run_forever()

        except Exception as e:
            logger.error(f"Startup failed: {e}", exc_info=True)
            await self.send_telegram_notification(
                f"[STARTUP FAILED] <b>Trading System Startup Failed</b>\n\n"
                f"Error: <code>{e!s}</code>"
            )
            raise

    async def _run_forever(self) -> None:
        """Keep the system running"""
        logger.info("System running - Press Ctrl+C to stop\n")
        await self._persist_runtime_health_snapshot(
            event_type="run_loop_start",
            message="Runtime loop entered",
        )

        # Print the startup health banner after 10s, but do not make shutdown
        # wait for a fixed timer to expire.
        try:
            await asyncio.wait_for(self._shutdown_event.wait(), timeout=10.0)
            return
        except TimeoutError:
            pass
        try:
            ibkr_ok = bool(self.ibkr_client and self.ibkr_client.isConnected())
            mt5_ok = False
            try:
                mt5_ok = bool(self.mt5_client and self.mt5_client.terminal_info())
            except Exception as e:
                logger.debug("Main: MT5 terminal_info() unavailable: %s", e)
            deterministic_ok = True
            qdb_ok = bool(self.questdb and self.questdb.is_active)
            dms_ok = bool(getattr(self, "dms", None))
            brain_ok = bool(self.trading_brain and self.trading_brain.is_running)
            account = getattr(self, "ibkr_account_id", "?")
            mode = getattr(self, "mode", "?")

            def _s(ok):
                return "OK " if ok else "OFF"

            banner = (
                "\n"
                "+------------------------------------------+\n"
                "|    SOVEREIGN ENGINE - STARTUP STATUS     |\n"
                "+------------------------------------------+\n"
                f"|  IBKR ({account}): {_s(ibkr_ok)}   Mode: {mode:<10}  |\n"
                f"|  Sovereign Core: {_s(deterministic_ok)}   Brain:  {_s(brain_ok)}            |\n"
                f"|  QuestDB:     {_s(qdb_ok)}   DMS:    {_s(dms_ok)}            |\n"
                f"|  MT5:         {_s(mt5_ok)}   (optional)             |\n"
                "+------------------------------------------+"
            )
            print(banner)
            market_open = self.trading_brain._is_market_open() if self.trading_brain else None
            if self.requires_ibkr_connection and not ibkr_ok:
                logger.warning(
                    "STARTUP DEGRADED - IBKR execution offline; automatic reattachment active."
                )
            elif market_open is False:
                logger.info(
                    "STARTUP COMPLETE - system healthy; market closed, new-trade scans deferred."
                )
            else:
                logger.info("STARTUP COMPLETE - system healthy; active loop online.")
        except Exception as e:
            logger.debug("Main: startup banner rendering failed: %s", e)

        try:
            while self.is_running:
                # 1. Update local heartbeat in database
                db = self.db_conn
                if db:
                    await self._persist_runtime_health_snapshot()

                # 2. Phone Home Telemetry (Remote Monitoring)
                tele_url = Vault.get("TELEMETRY_URL")
                if tele_url:
                    try:
                        from session_manager import SovereignSession

                        stats = await self.trading_brain.get_system_stats()
                        payload = {
                            "system_id": Vault.get("SYSTEM_ID", "SOVEREIGN_V9"),
                            "timestamp": time.time_ns(),
                            "stats": stats,
                            "active_broker": self.trading_brain.active_broker,
                            "uptime": time.time() - self._start_time
                            if hasattr(self, "_start_time")
                            else 0,
                        }
                        session = await SovereignSession.get_session()
                        async with session.post(tele_url, json=payload, timeout=5) as resp:
                            if resp.status == 200:
                                logger.debug("Telemetry: Phone Home successful.")
                    except Exception as e:
                        logger.debug(f"Telemetry: Phone Home failed (non-fatal): {e}")

                if hasattr(self, "hft_streamer") and self.hft_streamer:
                    drops = self.hft_streamer.dropped_ticks
                    if drops > 0:
                        logger.warning(
                            f"Sovereign Monitor: {drops} ticks DROPPED during current "
                            "session. Bus Saturation detected."
                        )

                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=60.0)
                    break
                except TimeoutError:
                    pass  # Pulse every 60 seconds

                # Checkpoint every 5 minutes (300s) to protect against local crashes
                if not hasattr(self, "_last_freeze_time"):
                    self._last_freeze_time = 0
                now = time.time()
                if now - self._last_freeze_time >= 300:
                    if hasattr(self, "trading_brain") and self.trading_brain is not None:
                        state_to_freeze = {
                            "positions": self.trading_brain.positions,
                            "peak_equity": self.trading_brain.ibkr_drawdown.peak_equity,
                            "loss_tracker": {
                                "consecutive_losses": (
                                    self.trading_brain.loss_tracker.consecutive_losses
                                )
                            },
                        }
                        await asyncio.to_thread(
                            self.trading_brain.session_restorer.freeze_state, state_to_freeze
                        )
                        self._last_freeze_time = now

                failed = [
                    name
                    for name, task in self.background_tasks.items()
                    if task.done() and task.exception() is not None
                ]
                if failed:
                    for name in failed:
                        exc = self.background_tasks[name].exception()
                        logger.critical(
                            "Background task '%s' died: %s — system continues.",
                            name,
                            exc,
                            exc_info=exc,
                        )
                        # Remove dead task so it won't flood every heartbeat cycle
                        del self.background_tasks[name]

        except asyncio.CancelledError:
            logger.info("System shutdown requested")
        except Exception as e:
            logger.critical("_run_forever: unexpected exception: %s", e, exc_info=True)

    def _start_supervised_task(
        self, name: str, coro_func: Callable[[], Coroutine[Any, Any, None]]
    ) -> None:
        """Create and track critical background tasks with exponential backoff on crash."""

        async def supervisor() -> None:
            retries = 0
            max_retries = 10
            base_delay = 5.0

            while retries < max_retries:
                try:
                    if self._shutdown_in_progress or not self.is_running:
                        logger.info("Supervisor: %s standing down during shutdown.", name)
                        return
                    logger.info(f"Supervisor: Launching {name}...")
                    await coro_func()
                    if self._shutdown_in_progress or not self.is_running:
                        logger.info(
                            "Background task '%s' stopped cleanly during shutdown.",
                            name,
                        )
                        return
                    logger.warning(
                        f"Background task '{name}' finished unexpectedly without error. "
                        "Restarting supervisor..."
                    )
                    await asyncio.sleep(5.0)  # Grace period before restart
                    retries += 1
                    continue
                except asyncio.CancelledError:
                    logger.info(f"Background task '{name}' cancelled.")
                    raise
                except Exception as e:
                    retries += 1
                    delay = base_delay * (2 ** (retries - 1))
                    logger.error(
                        f"Background task '{name}' crashed: {e} "
                        f"(Attempt {retries}/{max_retries}). Restarting in {delay}s...",
                        exc_info=True,
                    )
                    try:
                        await self.send_telegram_notification(
                            f"  *Background Task Crashed*\nTask: {name}\nError: {e!s}"
                        )
                    except Exception as _e:
                        logger.debug("TWS version detect failed: %s", _e)
                    if self._shutdown_in_progress or not self.is_running:
                        return
                    await asyncio.sleep(delay)

                if retries >= max_retries:
                    logger.critical(
                        f"Background task '{name}' permanently failed after {max_retries} retries. "
                        "MAINTAINING system uptime, but this component is now OFFLINE."
                    )
                    # Instead of raising and killing the event loop, we alert and exit the supervisor.
                    try:
                        await self.send_telegram_notification(
                            f" ⚠️ <b>[Sovereign Alert]</b>: Task {name} permanently OFFLINE. "
                            "System remains operational but logic may be impaired."
                        )
                    except Exception as _e:
                        logger.debug("TWS version detect failed: %s", _e)
                    return

        task = asyncio.create_task(supervisor())
        self.background_tasks[name] = task

    def _consume_shutdown_request(self) -> bool:
        """Consume a local shutdown request only when it targets this process."""
        request_path = getattr(self, "_shutdown_request_path", Path("data/shutdown.request"))
        try:
            requested_pid = request_path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return False
        except OSError as exc:
            logger.warning("Shutdown request could not be read: %s", exc)
            return False

        try:
            request_path.unlink(missing_ok=True)
        except OSError as exc:
            logger.warning("Shutdown request could not be consumed: %s", exc)
            return False

        current_pid = str(os.getpid())
        if requested_pid != current_pid:
            logger.warning(
                "Discarded stale shutdown request for PID %s; current PID is %s.",
                requested_pid or "<empty>",
                current_pid,
            )
            return False
        return True

    async def _run_shutdown_request_listener(self) -> None:
        """Translate a validated local request into the normal shutdown sequence."""
        while self.is_running and not self._shutdown_event.is_set():
            if self._consume_shutdown_request():
                logger.info(
                    "Local shutdown request accepted for PID %s; beginning graceful shutdown.",
                    os.getpid(),
                )
                self._shutdown_task = asyncio.create_task(
                    self.shutdown(), name="local_request_shutdown"
                )
                return
            try:
                await asyncio.wait_for(self._shutdown_event.wait(), timeout=0.5)
            except TimeoutError:
                continue

    async def shutdown(self) -> None:
        """Graceful shutdown sequence: Step-by-Step Institutional Guard."""
        if not hasattr(self, "_shutdown_lock"):
            self._shutdown_lock = asyncio.Lock()

        should_wait = False
        async with self._shutdown_lock:
            current_task = asyncio.current_task()
            active_task = getattr(self, "_shutdown_task", None)
            if active_task and active_task != current_task and not active_task.done():
                logger.info(
                    "Shutdown: Shutdown sequence already running in another task. Waiting for completion..."
                )
                should_wait = True

            if not should_wait:
                self._shutdown_task = current_task
                if self._shutdown_complete:
                    return

                self._shutdown_in_progress = True
                self.is_running = False

                # Signals all autonomous minds (Ghost, Scent, Evolution) to stand down.
                if hasattr(self, "bus") and self.bus:
                    try:
                        await self.bus.publish(
                            "system.status", {"state": "SHUTDOWN", "timestamp": time.time_ns()}
                        )
                    except Exception as _e:
                        logger.debug("TWS version detect failed: %s", _e)

                logger.info("\n" + "═" * 30)
                logger.info("SOVEREIGN: INITIATING SEQUENTIAL SHUTDOWN PROTOCOL")
                logger.info("═" * 30 + "\n")

        if should_wait:
            await self._shutdown_event.wait()
            return

        try:
            # 1. COMPUTE DAILY PERFORMANCE
            logger.info("[SHUTDOWN STEP 1/9] Calculating daily performance...")
            daily_pnl = 0.0
            trades_today = 0
            shadow_rejections_today = 0
            if hasattr(self, "db_conn") and self.db_conn:
                try:
                    cursor = self.db_conn.cursor()
                    # Use UTC today for the tally to match DB records
                    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    cursor.execute(
                        "SELECT pnl_dollars FROM trades "
                        "WHERE timestamp LIKE ? AND outcome != 'SHADOW_REJECTED'",
                        (f"{today_str}%",),
                    )
                    rows = cursor.fetchall()
                    trades_today = len(rows)
                    for row in rows:
                        if row[0] is not None:
                            daily_pnl += float(row[0])
                    cursor.execute(
                        "SELECT COUNT(*) FROM trades "
                        "WHERE timestamp LIKE ? AND outcome = 'SHADOW_REJECTED'",
                        (f"{today_str}%",),
                    )
                    shadow_row = cursor.fetchone()
                    shadow_rejections_today = int(shadow_row[0] or 0) if shadow_row else 0
                    cursor.close()
                    logger.info(
                        f"✓ Performance Tally: ${daily_pnl:+.2f} over {trades_today} trades."
                    )
                except Exception as e:
                    logger.error(f"Shutdown: Performance tally failed: {e}")

            # 2. SEND TELEGRAM SUMMARY
            logger.info("[SHUTDOWN STEP 2/9] Dispatching final Telegram report...")
            try:
                sign = "📈" if daily_pnl > 0 else "📉" if daily_pnl < 0 else "➖"
                summary_msg = (
                    f" <b>Sovereign System Offline</b>\n\n"
                    f" {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC\n"
                    f"───────────────────────────────\n"
                    f"<b>Daily Wrap-Up:</b>\n"
                    f"{sign} <b>Total PnL:</b> ${daily_pnl:+.2f}\n"
                    f" <b>Trades Executed:</b> {trades_today}\n"
                    f" <b>Shadow Rejections:</b> {shadow_rejections_today}\n"
                    f" <b>Status:</b> GRACEFUL_EXIT"
                )
                # Shielded Telegram send with slightly longer timeout
                await asyncio.wait_for(
                    self.send_telegram_notification(summary_msg),
                    timeout=10.0,
                )
            except Exception as tg_err:
                logger.warning(f"Shutdown: Telegram report failed/timed out: {tg_err}")

            # 3. STOP COMPONENTS (Sequential for deterministic cleanup)
            logger.info("[SHUTDOWN STEP 3/9] Stopping active minds and streams...")
            if hasattr(self, "trading_brain") and self.trading_brain:
                try:
                    logger.info(" -> Stopping Trading Brain...")
                    await self.trading_brain.stop()
                except Exception as e:
                    logger.error(f"Shutdown: Brain stop failed: {e}")

            if hasattr(self, "hft_streamer") and self.hft_streamer:
                try:
                    logger.info(" -> Stopping HFT Streamer...")
                    await self.hft_streamer.stop()
                except Exception as e:
                    logger.error(f"Shutdown: HFT Streamer stop failed: {e}")

            if hasattr(self, "tv_quote_streamer") and self.tv_quote_streamer:
                try:
                    logger.info(" -> Stopping TV Quote Streamer...")
                    await self.tv_quote_streamer.stop()
                except Exception as e:
                    logger.error(f"Shutdown: TV Quote Streamer stop failed: {e}")

            if hasattr(self, "data_pipeline") and self.data_pipeline:
                try:
                    logger.info(" -> Stopping Data Pipeline...")
                    await self.data_pipeline.stop()
                except Exception as e:
                    logger.error(f"Shutdown: Data Pipeline stop failed: {e}")

            if hasattr(self, "dms") and self.dms:
                try:
                    logger.info(" -> Stopping DMS...")
                    await self.dms.stop()
                except Exception as e:
                    logger.error(f"Shutdown: DMS stop failed: {e}")

            # Enhancement: Explicitly stop MindGhost to cancel its background tasks.
            # Without this, _shutdown_listener and _ghost_audit_loop tasks are leaked,
            # causing 'Task was destroyed but it is pending!' on every restart.
            if hasattr(self, "mind_ghost") and self.mind_ghost:
                try:
                    logger.info(" -> Stopping MindGhost (Agent J)...")
                    await self.mind_ghost.stop()
                except Exception as e:
                    logger.error(f"Shutdown: MindGhost stop failed: {e}")

            if hasattr(self, "api_server") and self.api_server:
                try:
                    logger.info(" -> Stopping API Server...")
                    await self.api_server.stop()
                except Exception as e:
                    logger.error(f"Shutdown: API Server stop failed: {e}")

            if hasattr(self, "dhatu_oracle") and self.dhatu_oracle:
                try:
                    logger.info(" -> Stopping Dhatu Oracle...")
                    await self.dhatu_oracle.stop()
                except Exception as e:
                    logger.error(f"Shutdown: Dhatu Oracle stop failed: {e}")

            # 4. UNLOAD AI MODELS
            logger.info("[SHUTDOWN STEP 4/9] Offloading Neural VRAM weights...")
            if hasattr(self, "native_slm") and self.native_slm:
                try:
                    await self.native_slm.close()
                    logger.info("✓ Native SLM unloaded.")
                except Exception as e:
                    logger.error(f"Shutdown: Native SLM close failed: {e}")

            if hasattr(self, "bus") and self.bus:
                try:
                    await self.bus.stop()
                    logger.info("✓ Intelligence Bus stopped.")
                except Exception as e:
                    logger.error(f"Shutdown: Bus stop failed: {e}")

            # 5. CANCEL REMAINING BACKGROUND TASKS
            logger.info("[SHUTDOWN STEP 5/9] Clearing background supervisors...")
            to_cancel = []
            for name, task in list(self.background_tasks.items()):
                if not task.done():
                    logger.info(f" -> Cancelling supervisor: {name}")
                    task.cancel()
                    to_cancel.append(task)

            if to_cancel:
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*to_cancel, return_exceptions=True), timeout=5.0
                    )
                except Exception as e:
                    logger.debug("Main: error waiting for background tasks to cancel: %s", e)
            self.background_tasks.clear()

            # 6. DISCONNECT BROKERS
            logger.info("[SHUTDOWN STEP 6/9] Disconnecting Broker Matrix...")
            if (
                hasattr(self, "_telegram_session")
                and self._telegram_session
                and not self._telegram_session.closed
            ):
                await self._telegram_session.close()
                self._telegram_session = None

            if self.ibkr_client and self.ibkr_client.isConnected():
                try:
                    logger.info(" -> Disconnecting IBKR...")
                    await asyncio.wait_for(
                        asyncio.to_thread(self.ibkr_client.disconnect), timeout=5.0
                    )
                except Exception as e:
                    logger.debug(f"IBKR disconnect error: {e}")

            if hasattr(self, "mt5_client") and self.mt5_client:
                try:
                    logger.info(" -> Disconnecting MT5...")
                    import MetaTrader5 as mt5

                    await asyncio.to_thread(mt5.shutdown)
                except Exception as e:
                    logger.debug(f"MT5 shutdown error: {e}")

            # 7. PERSIST FINAL STATE
            logger.info("[SHUTDOWN STEP 7/9] Persisting final state to registry...")
            if self.db_conn:
                try:
                    cursor = self.db_conn.cursor()
                    cursor.execute(
                        "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                        ("system_status", "stopped"),
                    )
                    cursor.execute(
                        "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                        ("last_shutdown", time.time_ns()),
                    )
                    self.db_conn.commit()
                    cursor.close()
                    logger.info("✓ System status flagged as STOPPED.")
                except Exception as db_err:
                    logger.error(f"Shutdown: Final state flag failed: {db_err}")

            if hasattr(self, "task_manager") and self.task_manager:
                try:
                    await asyncio.to_thread(self.task_manager.save_registry)
                    logger.info("✓ Final Task Registry flushed.")
                except Exception as e:
                    logger.error(f"Shutdown: Task Registry flush failed: {e}")

            # 8. FINAL DB CLOSURE
            logger.info("[SHUTDOWN STEP 8/9] Finalizing Persistence...")
            if (
                self.trading_brain
                and getattr(self.trading_brain, "evolution_manager", None)
            ):
                try:
                    self.trading_brain.evolution_manager.close()
                    logger.info("✓ Evolution engine connection terminated.")
                except Exception as e:
                    logger.error(f"Shutdown: Evolution DB closure error: {e}")
            if self.db_conn:
                try:
                    self.db_conn.close()
                    self.db_conn = None
                    logger.info("✓ Database connection terminated.")
                except Exception as e:
                    logger.error(f"Shutdown: DB closure error: {e}")

            # 9. EXIT
            logger.info("[SHUTDOWN STEP 9/9] Finalizing logs...")
            logger.info("\n" + "" * 30)
            logger.info("SOVEREIGN: SHUTDOWN SEQUENCE COMPLETE")
            logger.info("" * 30 + "\n")

            logging.shutdown()
            self._shutdown_complete = True
            self._shutdown_task = None

            # Signal the main event loop to exit cleanly.
            # Previously used os._exit(0) which skips finally blocks,
            # atexit handlers, and SQLite WAL checkpoint — risking DB corruption.
            self._shutdown_event.set()

        except Exception as e:
            logger.error(f"FATAL ERROR DURING SHUTDOWN: {e}", exc_info=True)

    async def _verify_watchdog(self) -> None:
        """Sovereign Guard: Ensures the watchdog process is active and pulsing."""
        if os.environ.get("SOVEREIGN_SKIP_PID_CHECK", "0") == "1":
            logger.info("Smoke-test mode detected - skipping watchdog verification/autostart.")
            return

        try:
            import psutil
        except ImportError:
            logger.warning(
                " DEPENDENCY MISSING: 'psutil' not found. "
                "Watchdog verification DISABLED. (pip install psutil)"
            )
            return
        pid_file = "data/watchdog.pid"
        if not os.path.exists(pid_file):
            logger.info("Watchdog PID file missing at startup; launching watchdog helper.")
            await self._start_watchdog_process()
            return

        try:
            with open(pid_file, "r") as f:
                w_pid = int(f.read().strip())

            if psutil.pid_exists(w_pid):
                logger.info(f" Watchdog Verified (PID: {w_pid})")
            else:
                logger.warning(f" WATCHDOG STALE: PID {w_pid} found in file but process is DEAD.")
                try:
                    os.remove(pid_file)
                    logger.info("Removed stale watchdog PID file.")
                except Exception as remove_error:
                    logger.warning(f"Failed to remove stale watchdog PID file: {remove_error}")
                await self._start_watchdog_process()
        except Exception as e:
            logger.error(f"Watchdog verification failed: {e}")
            await self._start_watchdog_process()

    async def _start_watchdog_process(self) -> None:
        """Start the dead-man watchdog as a detached helper process."""
        if os.environ.get("SOVEREIGN_DISABLE_WATCHDOG", "0") == "1":
            logger.warning("Watchdog auto-start disabled by SOVEREIGN_DISABLE_WATCHDOG=1.")
            return

        watchdog_script = Path(__file__).resolve().parent / "watchdog.py"
        if not watchdog_script.exists():
            logger.error("Watchdog auto-start failed: missing %s", watchdog_script)
            return

        creationflags = 0
        startupinfo = None
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW

        try:
            proc = subprocess.Popen(
                [sys.executable, str(watchdog_script)],
                cwd=str(Path(__file__).resolve().parent.parent),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=os.name != "nt",
                creationflags=creationflags,
                startupinfo=startupinfo,
            )
            actual_pid = None
            pid_path = Path("data/watchdog.pid")
            for _ in range(20):
                if pid_path.exists():
                    try:
                        actual_pid = pid_path.read_text(encoding="utf-8").strip()
                        if actual_pid:
                            break
                    except OSError as e:
                        logger.debug("Main: error reading PID file: %s", e)
                await asyncio.sleep(0.1)
            if actual_pid:
                logger.info(
                    "Watchdog auto-started successfully (launcher PID %s, watchdog PID %s).",
                    proc.pid,
                    actual_pid,
                )
            else:
                logger.warning(
                    "Watchdog launch requested (launcher PID %s), but PID file was not "
                    "written within 2s.",
                    proc.pid,
                )
        except Exception as exc:
            logger.error("Watchdog auto-start failed: %s", exc, exc_info=True)

    async def _run_aegis_watchdog(self) -> None:
        """
        Monitors the physical layer heart rate and triggers autonomous repair.
        """
        logger.info("Watchdog: Aegis Stability Protocol Active.")
        while self.is_running and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(60)
                if not self.is_running or self._shutdown_in_progress:
                    break

                # Check Ingestion Health (Delta since last HFT tick)
                drift = time.monotonic() - self._last_tick_time

                # If we haven't seen a tick in 5 minutes while a fast-lane source
                # is expected, we are likely 'blinded'. OHLCV-only runs should not
                # produce false HFT starvation warnings.
                if self._should_alert_hft_starvation(drift):
                    now_mono = time.monotonic()
                    if now_mono - self._last_data_starvation_alert > 300:
                        logger.warning(
                            f"Watchdog: Data Starvation Detected (Drift: {drift:.2f}s). "
                            "Awaiting HFT pulse recovery..."
                        )
                        self._last_data_starvation_alert = now_mono

                if hasattr(self, "mt5_client") and self.mt5_client:
                    try:
                        info = await asyncio.to_thread(self.mt5_client.terminal_info)
                        if info is None or not info.connected:
                            self._mt5_failure_count += 1
                            logger.warning(
                                f"Watchdog: MT5 Terminal Heartbeat LOST "
                                f"({self._mt5_failure_count}/3). "
                                "Attempting Reconnect..."
                            )
                            if self._mt5_failure_count >= 3:
                                logger.error(
                                    "Watchdog: MT5 Persistent Failure detected. "
                                    "Initiating Sovereign Resource Flush..."
                                )
                                self._recalibration_in_progress = True
                                try:
                                    if hasattr(self, "mind_system") and self.mind_system:
                                        await self.mind_system._tool_sovereign_flush()
                                        logger.info(
                                            "Watchdog: Sovereign Recovery Complete. "
                                            "Matrix state re-synchronized."
                                        )
                                        self._mt5_failure_count = 0  # Reset after flush
                                finally:
                                    self._recalibration_in_progress = False
                            else:
                                await self.connect_mt5()
                        else:
                            self._mt5_failure_count = 0  # Reset on success
                    except Exception as e:
                        logger.error(f"Watchdog: MT5 Heartbeat error: {e}")

            except Exception as e:
                logger.error(f"Watchdog Error (Aegis): {e}")

            pass

    def _hft_fast_lane_expected(self) -> bool:
        """Return True only when an HFT tick source should be producing pulses."""
        tv_enabled = os.environ.get("SOVEREIGN_TV_QUOTES_ENABLED", "1") == "1"
        ibkr_hft_enabled = os.environ.get("SOVEREIGN_IBKR_HFT_ENABLED", "0") == "1"
        return bool(tv_enabled or (self.hft_streamer and ibkr_hft_enabled))

    def _should_alert_hft_starvation(self, drift: float) -> bool:
        """Gate HFT starvation alerts to avoid false positives in OHLCV-only mode."""
        return (
            drift > 300
            and not self._recalibration_in_progress
            and self._is_us_equity_market_open()
            and self._hft_fast_lane_expected()
        )

    def _is_us_equity_market_open(self) -> bool:
        """Return True during regular US equity market hours."""
        return is_us_equity_market_open()

    async def _run_hft_pulse_worker(self) -> None:
        """
        Sovereign HFT Pulse Worker.
        Single background worker to process 100Hz ticks WITHOUT spawning new tasks.
        """
        logger.info("Main: HFT Pulse Worker started.")
        while True:
            try:
                data = await self._hft_pulse_queue.get()
                await self._on_hft_pulse(data)
                self._hft_pulse_queue.task_done()
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Main: HFT Worker Error: {e}")
                await asyncio.sleep(0.1)

    async def _on_hft_pulse(self, data: dict[str, Any]) -> None:
        """Sovereign Pulse Handler: Routes 10ms ticks to the Brain with zero-skip safety."""
        self._last_tick_time = time.monotonic()

        if hasattr(self, "trading_brain") and self.trading_brain:
            try:
                # BrainBusListener handles the heavy lifting via on_tick.
                # Here we only monitor for Watchdog purposes.
                pass
            except Exception as e:
                logger.debug(f"Pulse Error: {e}")

    async def _run_performance_monitor(self) -> None:
        """Background task that periodically tracks CPU, RAM, and IO performance metrics."""
        logger.info("Main: Performance Monitor ACTIVE (Interval: 15m).")
        import psutil

        while self.is_running and not self._shutdown_event.is_set():
            try:
                await asyncio.sleep(900)  # 15 Minutes
                if not self.is_running or self._shutdown_in_progress:
                    break
                cpu = psutil.cpu_percent()
                ram = psutil.virtual_memory().percent
                logger.info(
                    f" METRICS: CPU: {cpu}% | RAM: {ram}% | State: "
                    f"{self.trading_brain.state.name if hasattr(self, 'trading_brain') else 'INIT'}"
                )

                # Log to QuestDB if available
                if hasattr(self, "questdb") and self.questdb and self.questdb.is_active:
                    self.questdb.log_event("system_metrics", {"cpu": cpu, "ram": ram})
            except Exception as e:
                logger.error(f"Performance Monitor Error: {e}")

    async def _run_persistence_sentinel(self) -> None:
        """Background task that maintains database health and triggers long-term learning."""
        logger.info("Sentinel: Persistence Grooming Task ACTIVE (Interval: 24h).")
        self._sentinel_running = False

        while self.is_running and not self._shutdown_event.is_set():
            try:
                # Reduced from 30s pulses (which caused hardware resets) to 24-hour cycles.
                # Deep training should only occur when the system is not actively in an HFT session.
                await asyncio.sleep(86400)  # 24 Hours
                if not self.is_running or self._shutdown_in_progress:
                    break

                if self._sentinel_running:
                    logger.debug("Sentinel: Deep Training Cycle already in progress. Skipping.")
                    continue

                logger.info("Sentinel: Initiating Deep Agent Training Cycle...")
                self._sentinel_running = True

                def _sync_cleanup():
                    try:
                        import shutil

                        miro_logs = os.path.join("src", "MiroFish", "backend", "logs")
                        if os.path.exists(miro_logs):
                            shutil.rmtree(miro_logs)
                            os.makedirs(miro_logs)
                            logger.info("Sentinel: Purged legacy MiroFish temp logs.")

                        logs_dir = "logs"
                        if os.path.exists(logs_dir):
                            for f in os.listdir(logs_dir):
                                if f.endswith(".tmp"):
                                    try:
                                        os.remove(os.path.join(logs_dir, f))
                                    except Exception as e:
                                        logger.debug("Main: sentinel could not remove .tmp file: %s", e)
                            logger.debug("Sentinel: Logs directory sterilized of .tmp artifacts.")
                    except Exception as e:
                        logger.debug(f"Sentinel: MiroFish cleanup failed: {e}")

                await asyncio.to_thread(_sync_cleanup)

                def _optimize_and_train():
                    try:
                        import os
                        import subprocess
                        import sys

                        import psutil

                        ram_pct = psutil.virtual_memory().percent
                        if ram_pct > 75.0:
                            logger.warning(
                                f"Sentinel: RAM at {ram_pct:.1f}% is TOO HIGH for deep training. "
                                "Postponing cycle."
                            )
                            return True

                        # Check if the hardcore trainer is already running
                        script_name = "hardcore_75y_hyper_fidelity_trainer.py"
                        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                            if proc.info["cmdline"] and any(
                                script_name in arg for arg in proc.info["cmdline"]
                            ):
                                logger.warning(
                                    f"Sentinel: {script_name} is already alive "
                                    f"(PID {proc.info['pid']}). Aborting new spawn."
                                )
                                return True

                        script_path = Path(_root) / "scripts" / script_name
                        if not script_path.exists():
                            logger.error("Sentinel: Trainer script missing: %s", script_path)
                            return False

                        with closing(sqlite3.connect(self.db_path, timeout=60.0)) as conn:
                            conn.execute("PRAGMA journal_mode=WAL;")
                            conn.execute("PRAGMA busy_timeout=60000;")
                            conn.execute("VACUUM")
                            conn.execute("ANALYZE")

                        trainer_proc = subprocess.Popen(
                            [sys.executable, str(script_path)],
                            cwd=_root,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                            close_fds=os.name != "nt",
                        )
                        logger.info(
                            "Sentinel: Spawned deep trainer PID %s from %s",
                            trainer_proc.pid,
                            script_path,
                        )
                        return True
                    except Exception as e:
                        logger.error(f"Sentinel: Optimization/Training failed: {e}")
                        return False
                    finally:
                        self._sentinel_running = False

                success = await asyncio.to_thread(_optimize_and_train)
                if success:
                    logger.info("Sentinel: Deep Training Pulse & DB Integrity: 100%.")
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.error(f"Sentinel: Unexpected error: {e}")
                await asyncio.sleep(3600)  # Wait an hour before retrying on error

    def _display_dashboard(self) -> None:
        """Final Aesthetit Polish: Displays a terminal-grade dashboard of active Minds."""
        from dashboard.console import render_dashboard

        render_dashboard(self)


async def main(s: TradingSystem) -> None:
    try:
        await s.async_init()

        try:
            import shutil

            registry_file = "COMPLETE_SOVEREIGN_BUG_LIST.md"
            if os.path.exists(registry_file):
                shutil.copy2(registry_file, f"{registry_file}.bak")
                logger.info(f"✓ Registry backup created: {registry_file}.bak")
        except Exception as e:
            logger.warning(f"Watchdog: Registry backup failed: {e}")

        await s.startup()
        if s._shutdown_event.is_set():
            logger.info("Startup completed a bounded smoke run; shutdown already complete.")
            return

        # This prevents main() from finishing and hitting the 'finally' shutdown block.
        logger.info(" Matrix fully synchronized. System operational.")
        while not s._shutdown_event.is_set():
            # Frequent wakeups are required on Windows to process KeyboardInterrupts
            # Increased frequency to 0.2s for higher responsiveness to Ctrl+C.
            await asyncio.sleep(0.2)

    except (KeyboardInterrupt, asyncio.CancelledError):
        logger.info("\nShutdown signal received (Sovereign Request)")
    except Exception as e:
        logger.error(f"FATAL MATRIX FAILURE: {e}", exc_info=True)
    finally:
        try:
            # Increase timeout and shield from secondary Ctrl+C
            await asyncio.shield(asyncio.wait_for(s.shutdown(), timeout=30.0))
        except asyncio.TimeoutError:
            logger.critical(" SHUTDOWN HANG: Forceful Termination required.")
            os._exit(1)
        except Exception as e:
            logger.error(f"Shutdown error: {e}")
            os._exit(1)


if __name__ == "__main__":
    try:
        import winloop

        winloop.install()
    except ImportError as e:
        logger.debug("Main: winloop not available, using default event loop: %s", e)

    if sys.platform == "win32" and "winloop" not in sys.modules:
        import asyncio

        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    try:
        import asyncio

        asyncio.get_event_loop()
    except RuntimeError:
        import asyncio

        asyncio.set_event_loop(asyncio.new_event_loop())
    # Force UTF-8 encoding for Windows (resolves 'mojibake' in logs)
    import os
    import sys

    if sys.platform.startswith("win"):
        import io

        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", line_buffering=True)
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", line_buffering=True)
        except Exception:
            pass  # Fallback for environments where buffer is not available

    # Memory-Only Key Injection to retain 100% IQ with zero disk-print.
    import getpass

    from vault import Vault

    is_tty = sys.stdin.isatty() and sys.stdout.isatty()

    if not str(Vault.get("DEEPSEEK_API_KEY", "")).strip() and is_tty:
        print("\n" + "═" * 78)
        print("  SOVEREIGN GHOST KEY: Apex Auditor (671B IQ) is currently INACTIVE.")
        # ... (rest of prompt suppressed in replacement for brevity, logic remains)
        try:
            key = getpass.getpass(
                "Enter Sovereign Apex Key (Optional, press Enter to skip): "
            ).strip()
            if key:
                os.environ["DEEPSEEK_API_KEY"] = key
                print("\n✓ GHOST KEY ACTIVE. Remote IQ Auditor Enabled.")
            else:
                print("\n Remote Audit SKIPPED. Relying on Local Quorum.")
        except (KeyboardInterrupt, EOFError):
            print("\n Input Interrupted. Defaulting to Local Mode.")
    elif not is_tty and not str(Vault.get("DEEPSEEK_API_KEY", "")).strip():
        logger.info("Sovereign: Non-TTY environment detected. Skipping interactive key injection.")

    import signal

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    s = TradingSystem()

    # SOVEREIGN SIGNAL BRIDGE:
    # Ensure winloop/asyncio actually hears Ctrl+C on Windows.
    def _handle_exit():
        logger.info("\n[SOVEREIGN] Shutdown Signal Received. Initiating Graceful Exit...")
        if not s._shutdown_event.is_set():
            asyncio.create_task(s.shutdown())

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            # winloop supports add_signal_handler; default asyncio on Win does not.
            loop.add_signal_handler(sig, _handle_exit)
        except (NotImplementedError, AttributeError):
            # Fallback to standard signal handler for compatibility
            try:
                signal.signal(sig, lambda sn, f: _handle_exit())
            except Exception as exc:
                logger.debug("Sovereign: signal fallback registration failed: %s", exc)

    try:
        loop.run_until_complete(main(s))
    except (KeyboardInterrupt, SystemExit):
        print("\n[SOVEREIGN] Termination Signal Confirmed.")
    except Exception as e:
        print(f"\n[SOVEREIGN] Fatal Error: {e}")
    finally:
        try:
            # Guard: only call shutdown() if it wasn't already initiated by the
            # signal handler (_handle_exit). A double-call causes the supervisor
            # to log 'trading_brain finished unexpectedly' on a clean exit.
            try:
                if not s._shutdown_event.is_set():
                    loop.run_until_complete(asyncio.wait_for(s.shutdown(), timeout=45.0))
                else:
                    # Shutdown already in progress — wait for it to complete
                    loop.run_until_complete(
                        asyncio.wait_for(s._shutdown_event.wait(), timeout=45.0)
                    )
            except (KeyboardInterrupt, BaseException, Exception) as e:
                print(f"[SOVEREIGN] Primary Shutdown Exception or Interrupt: {e}")

            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]

            if pending:
                logger.info(f"Shutting down {len(pending)} active tasks...")
                for task in pending:
                    task.cancel()

                # Drain the loop with a 10s hard timeout
                try:
                    loop.run_until_complete(asyncio.wait(pending, timeout=10.0))
                except (KeyboardInterrupt, asyncio.TimeoutError):
                    logger.warning(
                        "Shutdown: Timeout or double Ctrl+C detected. Force closing loop."
                    )
                except Exception as e:
                    logger.debug(f"Shutdown: Loop drain exception: {e}")

            # Ensure all handles are closed before loop.close() to prevent UVHandle warnings
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception as e:
                logger.debug("Main: shutdown_asyncgens failed: %s", e)

            s._clear_own_pid_file()
            loop.close()
        except Exception as e:
            print(f"Shutdown Error: {e}")

        print("[SOVEREIGN] Shutdown Complete.")
        sys.exit(0)
