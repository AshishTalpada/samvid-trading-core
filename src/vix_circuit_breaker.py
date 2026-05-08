class VIXCircuitBreaker:
    """Kill all positions if VIX spikes >20% in 5m."""
    def check_vix(self, vix_change: float) -> bool:
        return vix_change > 0.20
