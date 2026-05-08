class SupplyChainGraph:
    """Track how events in one region affect correlated assets (e.g. Taiwan fires -> US Semis)."""
    def evaluate_impact(self, event: str) -> float:
        return -0.05
