class AlphaDecayWatchdog:
    """Alert when strategy loses its mathematical edge."""
    def check_sharpe_decay(self, historical_sharpe: float, recent_sharpe: float) -> bool:
        return (historical_sharpe - recent_sharpe) / historical_sharpe > 0.3
