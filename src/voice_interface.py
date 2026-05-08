class VoiceInterface:
    """NL Voice Control - Speed of command via STT."""
    def parse_command(self, text: str) -> dict:
        if "risk-off" in text.lower():
            return {"action": "RISK_OFF"}
        return {}
