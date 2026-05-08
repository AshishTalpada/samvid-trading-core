class AlphaWatchdog:
    """Alert when a strategy starts losing its edge."""
    def check_decay(self, strategy_id: str, win_rate: float) -> bool:
        return win_rate < 0.4
