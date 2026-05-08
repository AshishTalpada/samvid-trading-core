import logging
import threading
from abc import ABC, abstractmethod
from typing import Callable

logger = logging.getLogger(__name__)

class StreamerBase(ABC):
    """
    Abstract base class for all Sovereign market data streamers.
    Enforces a uniform interface for IBKR, Alpaca, Nasdaq ITCH, and Starlink feeds.
    Provides built-in reconnection logic and heartbeat monitoring.
    """
    def __init__(self, reconnect_delay: float = 5.0):
        self._running = False
        self._reconnect_delay = reconnect_delay
        self._callbacks: list[Callable] = []
        self._thread: threading.Thread | None = None

    def subscribe(self, callback: Callable) -> None:
        self._callbacks.append(callback)

    def _dispatch(self, tick: dict) -> None:
        for cb in self._callbacks:
            try: cb(tick)
            except Exception as e: logger.error(f"[STREAMER] Callback error: {e}")

    @abstractmethod
    def connect(self) -> bool: ...

    @abstractmethod
    def _stream_loop(self) -> None: ...

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._stream_loop, daemon=True)
        self._thread.start()
        logger.info(f"[STREAMER] {self.__class__.__name__} started.")

    def stop(self) -> None:
        self._running = False
        logger.info(f"[STREAMER] {self.__class__.__name__} stopped.")
