import numpy as np


class SentimentVol:
    def calculate_svi(self, sentiment_scores: list[float]) -> float:
        if len(sentiment_scores) < 2:
            return 0.0
        return float(np.std(sentiment_scores))
