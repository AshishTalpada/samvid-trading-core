import logging
import threading
import time
from typing import Callable, Dict

logger = logging.getLogger(__name__)


class DataPrefetcher:
    """
    Predictively pulls ticker data into RAM before the AI asks for it.
    Uses a background thread to continuously refresh the most-watched symbols,
    so data is always in memory when the quorum cycle fires.
    """

    def __init__(self, refresh_interval_s: float = 2.0):
        self._cache: Dict[str, dict] = {}
        self._fetch_fns: Dict[str, Callable] = {}
        self._interval = refresh_interval_s
        self._running = False
        self._thread: threading.Thread | None = None

    def register(self, symbol: str, fetch_fn: Callable[[], dict]) -> None:
        self._fetch_fns[symbol] = fetch_fn
        logger.debug(f"[PREFETCHER] Registered: {symbol}")

    def get(self, symbol: str) -> dict | None:
        return self._cache.get(symbol)

    def _prefetch_loop(self) -> None:
        while self._running:
            for symbol, fn in list(self._fetch_fns.items()):
                try:
                    self._cache[symbol] = fn()
                except Exception as e:
                    logger.warning(f"[PREFETCHER] {symbol} fetch failed: {e}")
            time.sleep(self._interval)

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._prefetch_loop, daemon=True, name="Prefetcher")
        self._thread.start()
        logger.info("[PREFETCHER] Started.")

    def stop(self) -> None:
        self._running = False
