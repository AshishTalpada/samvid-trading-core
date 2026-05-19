import logging
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class WatchdogPulse:
    """
    Tracks user presence via physical heartbeats / interactions.
    If the operator steps away (or biometric pulse ceases), the system
    automatically degrades to a lower-risk profile, cutting position sizes
    and tightening stops to prevent unsupervised black-swan liquidation.
    """

    def __init__(self, idle_timeout_secs: int = 300, degrade_factor: float = 0.5):
        self.timeout = idle_timeout_secs
        self.degrade_factor = degrade_factor
        self.last_heartbeat = time.time()
        self.active = True

    def pulse(self, source: str = "ui_interaction") -> None:
        self.last_heartbeat = time.time()
        if not self.active:
            logger.info(f"[WATCHDOG] User returned via {source}. Restoring full risk parameters.")
            self.active = True

    def is_user_away(self) -> bool:
        elapsed = time.time() - self.last_heartbeat
        away = elapsed > self.timeout
        if away and self.active:
            logger.warning(
                f"[WATCHDOG] User away for {elapsed:.0f}s. Degrading risk parameters by {self.degrade_factor * 100}%."
            )
            self.active = False
        return away

    def risk_multiplier(self) -> float:
        return 1.0 if not self.is_user_away() else self.degrade_factor

    def status(self) -> Dict[str, Any]:
        return {
            "is_away": self.is_user_away(),
            "time_since_pulse": round(time.time() - self.last_heartbeat, 1),
            "current_multiplier": self.risk_multiplier(),
        }
