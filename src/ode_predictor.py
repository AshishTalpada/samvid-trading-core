class NeuralODE:
    """Continuous-time price prediction for HFT exits."""
    def predict_next_tick(self, state: list[float]) -> float:
        return state[-1] if state else 0.0
