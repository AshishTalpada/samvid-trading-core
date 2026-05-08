class SelfReferentialPredictor:
    def __init__(self):
        self.past_impacts = []

    def add_impact(self, size: float, price_move: float):
        self.past_impacts.append((size, price_move))

    def adjust_prediction(self, base_pred: float, intended_size: float) -> float:
        if not self.past_impacts: return base_pred
        avg_move_per_size = sum(m/s for s, m in self.past_impacts if s > 0) / len(self.past_impacts)
        return base_pred - (intended_size * avg_move_per_size)
