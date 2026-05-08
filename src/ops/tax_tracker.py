class TaxLiabilityTracker:
    """Knowing your tax bill in real-time as you trade."""
    def __init__(self, tax_rate: float = 0.37):
        self.rate = tax_rate
        self.owed = 0.0

    def log_trade(self, realized_pnl: float):
        if realized_pnl > 0:
            self.owed += realized_pnl * self.rate
