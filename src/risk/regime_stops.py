class RegimeStops:
    """ATR-based stops that adapt to BULL/BEAR."""
    def calculate_stop(self, atr: float, regime: str) -> float:
        if regime == "BEAR":
            return atr * 1.5
        return atr * 3.0
