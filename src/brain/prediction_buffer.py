import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

class PredictionBuffer:
    """Pre-calculates the next likely decision branch to minimize latency."""
    def __init__(self):
        self.buffer: Dict[str, Any] = {}

    def precompute(self, ticker: str, predicted_signal: str, predicted_size: float) -> None:
        self.buffer[ticker] = {"signal": predicted_signal, "size": predicted_size}
        logger.debug(f"Pre-buffered {ticker}: {predicted_signal} x {predicted_size:.2f}")

    def consume(self, ticker: str) -> Dict[str, Any] | None:
        return self.buffer.pop(ticker, None)
