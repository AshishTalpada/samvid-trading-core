class ContinuousPRoR:
    """
    Item 186: Continuous Probability of Ruin (PRoR)
    Live calculation of bankruptcy probability based on dynamic win rate and payoff ratio.
    """
    def calculate_pror(self, win_rate: float, payoff_ratio: float, risk_per_trade: float) -> float:
        """
        Calculates the theoretical Probability of Ruin (PRoR) using the risk of ruin formula.
        
        Args:
            win_rate: Decimal win rate (e.g., 0.55).
            payoff_ratio: Average win / Average loss.
            risk_per_trade: Percentage of account risked per trade (e.g., 0.02 for 2%).
            
        Returns:
            Probability of Ruin (0.0 to 1.0).
        """
        # Edge cases
        if win_rate >= 1.0:
            return 0.0
        if win_rate <= 0.0:
            return 1.0
            
        loss_rate = 1.0 - win_rate
        
        # If expectancy is negative, ruin is inevitable (100%)
        expectancy = (win_rate * payoff_ratio) - loss_rate
        if expectancy <= 0:
            return 1.0
            
        # Simplified Kelly-esque risk of ruin formula:
        # P(Ruin) = [ (1 - Edge) / (1 + Edge) ] ^ (1 / Risk%)
        # For a standard coin flip style model:
        edge = (win_rate * (1 + payoff_ratio)) - 1
        if edge <= 0:
            return 1.0
            
        base = (1 - edge) / (1 + edge)
        
        # Ensure base is strictly positive to prevent complex numbers
        if base <= 0:
            return 0.0
            
        try:
            ruin = base ** (1.0 / risk_per_trade)
            return min(1.0, float(ruin))
        except (OverflowError, ZeroDivisionError):
            return 1.0
