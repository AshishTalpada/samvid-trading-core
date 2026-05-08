import logging
logger = logging.getLogger(__name__)

class LogisticsSim:
    """Models how supply chain disruptions ripple through commodity and chip sectors."""
    SECTOR_DEPENDENCIES = {
        "citrus": ["OJ_FUTURES", "GROCERY_RETAIL"],
        "chips": ["NVDA", "AMD", "AAPL", "MSFT"],
        "oil": ["AIRLINES", "SHIPPING", "PLASTICS"],
    }

    def get_affected_tickers(self, disruption_type: str) -> list[str]:
        affected = self.SECTOR_DEPENDENCIES.get(disruption_type.lower(), [])
        if affected:
            logger.info(f"Logistics disruption in '{disruption_type}' affects: {affected}")
        return affected
