class ReflexivityScale:
    """Adjust strategy if you become Too Large."""
    def check_size(self, aum: float) -> float:
        return max(0.1, 1000000.0 / (aum + 1.0))
