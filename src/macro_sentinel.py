class MacroSentinel:
    """Monitors macro thresholds and generates kill signals."""
    def __init__(self, vix_kill: float = 40.0, yield_spike: float = 0.50):
        self.vix_kill = vix_kill
        self.yield_spike = yield_spike

    def evaluate(self, vix: float, ten_yr_yield_change: float) -> bool:
        """Returns True if macro conditions warrant immediate risk-off."""
        return vix >= self.vix_kill or ten_yr_yield_change >= self.yield_spike
