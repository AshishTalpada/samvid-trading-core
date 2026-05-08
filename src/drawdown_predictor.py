class DrawdownPredictor:
    """Predict how long a losing streak will last."""
    def predict_duration(self, current_streak: int) -> int:
        return current_streak + 2
