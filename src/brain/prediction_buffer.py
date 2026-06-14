import logging
import threading
from collections import deque
from typing import Any, Deque, Dict, Optional

logger = logging.getLogger(__name__)


class PredictionBuffer:
    """
    Pre-computation buffer that calculates the next 3 decision branches
    before the market forces a decision, eliminating computation latency.
    Thread-safe using a deque with a configurable capacity.
    """

    def __init__(self, capacity: int = 8):
        self._capacity = capacity
        self._buffer: Deque[Dict[str, Any]] = deque(maxlen=capacity)
        self._lock = threading.Lock()

    def push(self, branch: Dict[str, Any]) -> None:
        with self._lock:
            self._buffer.append(branch)
            logger.debug(
                f"[PRED BUFFER] Pushed branch: {branch.get('scenario', '?')} ({len(self._buffer)}/{self._capacity})"
            )

    def pop_best(self) -> Optional[Dict[str, Any]]:
        with self._lock:
            if not self._buffer:
                return None
            # Find index of highest-probability branch; avoid O(n) dict equality in .remove()
            best_idx = max(
                range(len(self._buffer)),
                key=lambda i: self._buffer[i].get("probability", 0.0),
            )
            best = self._buffer[best_idx]
            del self._buffer[best_idx]
            logger.debug(
                f"[PRED BUFFER] Popped best: {best.get('scenario', '?')} p={best.get('probability', 0):.2f}"
            )
            return best

    def peek_all(self) -> list[Dict[str, Any]]:
        with self._lock:
            return list(self._buffer)

    def size(self) -> int:
        return len(self._buffer)
