class RegimeSlicer:
    """Adapts execution slicing strategy based on the current market regime."""
    REGIME_PARAMS = {
        "BULL":  {"slices": 5,  "urgency": 0.8},
        "BEAR":  {"slices": 15, "urgency": 0.3},
        "CHOP":  {"slices": 10, "urgency": 0.5},
    }

    def get_execution_params(self, regime: str) -> dict:
        return self.REGIME_PARAMS.get(regime, self.REGIME_PARAMS["CHOP"])
