class DeltaNeutralAlpha:
    def calculate_hedge_ratio(self, long_beta: float, short_beta: float) -> float:
        if short_beta == 0:
            return 1.0
        return abs(long_beta / short_beta)
