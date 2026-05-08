class NewsAgent:
    """AI parses Fed Minutes to adjust risk instantly."""
    def parse_minutes(self, text: str) -> float:
        if "hike" in text.lower():
            return -1.0
        return 1.0
