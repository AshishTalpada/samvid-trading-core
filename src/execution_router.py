import logging

logger = logging.getLogger(__name__)

class BrokerRouter:
    """Failover execution router between primary and backup brokers."""
    def __init__(self, primary: str = "IBKR", fallback: str = "ALPACA"):
        self.primary = primary
        self.fallback = fallback
        self.primary_healthy = True

    def mark_primary_down(self) -> None:
        self.primary_healthy = False
        logger.warning(f"Primary broker {self.primary} marked down. Routing to {self.fallback}.")

    def mark_primary_up(self) -> None:
        self.primary_healthy = True
        logger.info(f"Primary broker {self.primary} restored.")

    def get_active_broker(self) -> str:
        return self.primary if self.primary_healthy else self.fallback
