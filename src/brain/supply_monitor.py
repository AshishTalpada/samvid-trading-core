import logging
logger = logging.getLogger(__name__)

class SupplyMonitor:
    """Watches supplier financial health and alerts on bankruptcy risk."""
    def __init__(self, bankruptcy_z_threshold: float = 1.81):
        self.threshold = bankruptcy_z_threshold

    def calculate_altman_z(self, working_capital: float, total_assets: float,
                           retained_earnings: float, ebit: float,
                           market_cap: float, total_liabilities: float, revenue: float) -> float:
        if total_assets == 0 or total_liabilities == 0:
            return 0.0
        x1 = working_capital / total_assets
        x2 = retained_earnings / total_assets
        x3 = ebit / total_assets
        x4 = market_cap / total_liabilities
        x5 = revenue / total_assets
        return 1.2*x1 + 1.4*x2 + 3.3*x3 + 0.6*x4 + x5

    def is_distressed(self, z_score: float) -> bool:
        if z_score < self.threshold:
            logger.warning(f"Supplier distress detected: Z-score={z_score:.2f}")
            return True
        return False
