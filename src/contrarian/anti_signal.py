class AntiSignalTracker:
    """Generates contrarian signals by inverting systematically-wrong crowd signals."""
    def __init__(self, error_rate_threshold: float = 0.65):
        self.threshold = error_rate_threshold

    def evaluate(self, crowd_signal: str, crowd_error_rate: float) -> str:
        """Returns the anti-signal if the crowd is reliably wrong."""
        if crowd_error_rate >= self.threshold:
            return "BUY" if crowd_signal == "SELL" else "SELL" if crowd_signal == "BUY" else "NEUTRAL"
        return "NEUTRAL"
