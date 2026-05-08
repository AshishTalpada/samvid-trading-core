class CryptoBridge:
    """Uses BTC/ETH movements as leading indicators for tech sector risk appetite."""
    def get_risk_signal(self, btc_change_24h: float, eth_change_24h: float) -> str:
        composite = (btc_change_24h + eth_change_24h) / 2.0
        if composite > 0.05:
            return "RISK_ON"
        elif composite < -0.05:
            return "RISK_OFF"
        return "NEUTRAL"
