import logging
logger = logging.getLogger(__name__)

class LiquidCoolingPump:
    """Monitors direct-to-chip liquid cooling flow rates."""
    def get_flow_rate(self) -> float:
        return 1.5  # Gallons per minute
