class StressVeto:
    """Lock the user out if Revenge Trading detected."""
    def evaluate_trading_pattern(self, loss_streak: int) -> bool:
        return loss_streak > 3
