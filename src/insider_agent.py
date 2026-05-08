class InsiderAgent:
    def analyze_form4(self, buy_volume: float, sell_volume: float) -> str:
        if buy_volume > sell_volume * 3:
            return "STRONG_ACCUMULATION"
        elif sell_volume > buy_volume * 5:
            return "STRONG_DISTRIBUTION"
        return "NEUTRAL"
