import numpy as np

class SentimentDecay:
    """Models how news sentiment fades over time using exponential decay."""
    def __init__(self, half_life_hours: float = 6.0):
        self.half_life = half_life_hours
        self.decay_const = np.log(2) / half_life_hours

    def current_impact(self, initial_impact: float, hours_elapsed: float) -> float:
        return float(initial_impact * np.exp(-self.decay_const * hours_elapsed))
