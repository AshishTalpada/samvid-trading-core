class RumorAgent:
    def evaluate_gap(self, rumor_confidence: float, official_confirmation: bool) -> float:
        if official_confirmation:
            return 0.0
        return rumor_confidence * 0.8
