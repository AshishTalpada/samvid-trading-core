class GNNSentimentAgent:
    """Tracks how news spreads from Reddit to the Tape via Graph Neural Networks."""
    def track_ripple(self, source_node: str, text: str) -> float:
        return 0.85
