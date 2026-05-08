class TaxTracker:
    """Real-time tax liability calculator for active positions."""
    def __init__(self, short_term_rate: float = 0.37, long_term_rate: float = 0.20):
        self.short_rate = short_term_rate
        self.long_rate = long_term_rate

    def estimate_liability(self, realized_gains: float, holding_days: int) -> float:
        rate = self.long_rate if holding_days >= 365 else self.short_rate
        return max(0.0, realized_gains * rate)
