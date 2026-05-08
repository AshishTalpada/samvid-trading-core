class SECAgent:
    """Parses SEC filing keywords and flags anomalies."""
    DANGER_PHRASES = ["going concern", "material weakness", "restatement", "SEC investigation"]

    def analyze_filing(self, text: str) -> dict[str, bool | list[str]]:
        text_lower = text.lower()
        found = [p for p in self.DANGER_PHRASES if p in text_lower]
        return {"red_flag": len(found) > 0, "matches": found}
