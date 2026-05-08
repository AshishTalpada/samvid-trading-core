import logging
logger = logging.getLogger(__name__)

class PredictionMarketAgent:
    """Uses prediction market probabilities (e.g. Polymarket) as macro leading indicators."""
    def __init__(self, election_weight: float = 0.3, rate_weight: float = 0.7):
        self.election_weight = election_weight
        self.rate_weight = rate_weight

    def get_macro_probability(self, rate_cut_prob: float, election_stability_prob: float) -> float:
        composite = (rate_cut_prob * self.rate_weight + election_stability_prob * self.election_weight)
        logger.debug(f"Macro probability score: {composite:.2f}")
        return float(composite)
