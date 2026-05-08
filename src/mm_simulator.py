class MMSimulator:
    def predict_stop_hunt(self, current_price: float, retail_stops: list[float]) -> float | None:
        nearby_stops = [s for s in retail_stops if abs(s - current_price)/current_price < 0.02]
        if len(nearby_stops) > 100:
            return sum(nearby_stops) / len(nearby_stops)
        return None
