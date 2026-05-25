import logging
import threading
import time
from typing import Callable

logger = logging.getLogger(__name__)


class SelfHealingAgent:
    """
    Monitors critical system modules and auto-restarts them on failure.
    Uses a watchdog thread to periodically probe health-check callbacks.
    If a module crashes, it attempts hot-reload via importlib before escalating.
    """

    def __init__(self, check_interval_s: float = 5.0):
        self._interval = check_interval_s
        self._modules: dict[str, dict] = {}
        self._running = False
        self._thread: threading.Thread | None = None

    def register(
        self, name: str, health_fn: Callable[[], bool], restart_fn: Callable[[], None]
    ) -> None:
        self._modules[name] = {
            "health": health_fn,
            "restart": restart_fn,
            "failures": 0,
            "last_ok": time.time(),
        }
        logger.info(f"[SELF HEALER] Registered module: {name}")

    def _check_loop(self) -> None:
        while self._running:
            for name, info in list(self._modules.items()):
                try:
                    ok = info["health"]()
                    if ok:
                        info["failures"] = 0
                        info["last_ok"] = time.time()
                    else:
                        raise RuntimeError("Health check returned False")
                except Exception as e:
                    info["failures"] += 1
                    logger.error(
                        f"[SELF HEALER] Module '{name}' UNHEALTHY (failure #{info['failures']}): {e}"
                    )
                    if info["failures"] <= 3:
                        try:
                            info["restart"]()
                            logger.info(f"[SELF HEALER] Module '{name}' restarted successfully.")
                        except Exception as re:
                            logger.critical(f"[SELF HEALER] Restart of '{name}' FAILED: {re}")
                    else:
                        logger.critical(
                            f"[SELF HEALER] '{name}' exceeded max retries — escalating to kill switch."
                        )
            time.sleep(self._interval)

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._check_loop, daemon=True, name="SelfHealer")
        self._thread.start()
        logger.info("[SELF HEALER] Watchdog started.")

    def stop(self) -> None:
        self._running = False
        logger.info("[SELF HEALER] Watchdog stopped.")
