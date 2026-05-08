class TaxHarvester:
    def identify_harvest_candidates(self, positions: dict[str, float]) -> list[str]:
        return [ticker for ticker, pnl in positions.items() if pnl < -0.10]
