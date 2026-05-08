from src.knowledge_graph import KnowledgeGraph


class MacroTopology:
    """Pre-builds the macro knowledge graph with known market relationships."""
    def __init__(self):
        self.graph = KnowledgeGraph()
        self._seed()

    def _seed(self) -> None:
        relationships = [
            ("FED_RATE_HIKE", "TECH_SELLOFF"),
            ("FED_RATE_HIKE", "BANK_RALLY"),
            ("OIL_SPIKE", "AIRLINE_DROP"),
            ("OIL_SPIKE", "ENERGY_RALLY"),
            ("CHINA_SLOWDOWN", "COMMODITY_DROP"),
            ("DOLLAR_STRENGTH", "EM_SELLOFF"),
            ("TSMC_EARNINGS", "NVDA_MOVE"),
            ("TSMC_EARNINGS", "AAPL_MOVE"),
        ]
        for cause, effect in relationships:
            self.graph.add_relationship(cause, effect)

    def get_effects(self, event: str) -> set:
        return self.graph.get_ripple_effects(event)
