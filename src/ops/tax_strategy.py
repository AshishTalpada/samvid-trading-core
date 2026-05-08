class TaxOptimization:
    """Trade specifically to minimize capital gains tax."""
    def __init__(self):
        self.short_term_gains = 0.0
        self.long_term_gains = 0.0

    def calculate_wash_sale_risk(self, ticker: str, days_since_loss: int) -> bool:
        # IRS rule: Can't buy same security within 30 days of realizing a loss
        if days_since_loss <= 30:
            return True
        return False

    def harvest_losses(self, portfolio: dict) -> list[str]:
        # Return tickers currently operating at a loss to offset gains
        return [ticker for ticker, unrealized in portfolio.items() if unrealized < -1000]
