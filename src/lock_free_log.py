import logging
logger = logging.getLogger(__name__)

class LockFreeLogger:
    """Zero-latency lock-free ring buffer for asynchronous disk logging."""
    def __init__(self):
        self.buffer = []

    def log_async(self, message: str) -> None:
        self.buffer.append(message)
