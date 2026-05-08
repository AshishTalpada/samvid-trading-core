import numpy as np
import logging
logger = logging.getLogger(__name__)

class CorrelationMonitor:
    """Monitors rolling correlation between a symbol and its sector lead."""
    def __init__(self, decay_threshold: float = 0.3):
        self.decay_threshold = decay_threshold

    def should_exit(self, symbol_returns: list[float], sector_returns: list[float]) -> bool:
        if len(symbol_returns) < 10 or len(sector_returns) < 10:
            return False
        corr = float(np.corrcoef(symbol_returns[-20:], sector_returns[-20:])[0, 1])
        if corr < self.decay_threshold:
            logger.warning(f"Correlation decay detected: {corr:.2f}. Exiting position.")
            return True
        return False
