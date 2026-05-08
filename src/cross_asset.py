class CrossAssetLeader:
    def get_equity_signal(self, bond_yield_change: float, gold_change: float) -> str:
        if bond_yield_change < -0.05 and gold_change > 0.02:
            return "RISK_OFF"
        elif bond_yield_change > 0.02 and gold_change < -0.01:
            return "RISK_ON"
        return "NEUTRAL"
