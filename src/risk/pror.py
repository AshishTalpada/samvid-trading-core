class ContinuousPRoR:
    """Live calculation of bankruptcy probability based on dynamic win rate and payoff ratio."""
    def calculate_pror(self, win_rate: float, payoff_ratio: float, risk_per_trade: float) -> float:
        if win_rate >= 1.0:
            return 0.0
        if win_rate <= 0.0:
            return 1.0
        loss_rate = 1.0 - win_rate
        expectancy = (win_rate * payoff_ratio) - loss_rate
        if expectancy <= 0:
            return 1.0
        edge = (win_rate * (1 + payoff_ratio)) - 1
        if edge <= 0:
            return 1.0
        base = (1 - edge) / (1 + edge)
        if base <= 0:
            return 0.0
        try:
            return min(1.0, float(base ** (1.0 / risk_per_trade)))
        except (OverflowError, ZeroDivisionError):
            return 1.0
