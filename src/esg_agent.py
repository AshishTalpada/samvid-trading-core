import logging
logger = logging.getLogger(__name__)

class ESGAgent:
    """Calculates if ESG (Social/Environmental) scores correlate with stock outperformance."""
    def __init__(self, min_sample: int = 20):
        self.min_sample = min_sample

    def calculate_edge(self, esg_scores: list[float], stock_returns: list[float]) -> float:
        if len(esg_scores) < self.min_sample or len(stock_returns) < self.min_sample:
            return 0.0
        import numpy as np
        corr = float(np.corrcoef(esg_scores[:self.min_sample], stock_returns[:self.min_sample])[0, 1])
        logger.info(f"ESG-Return correlation: {corr:.3f}")
        return corr
