class DecisionLedger:
    def attribute(self, trade_id: str, feature_weights: dict) -> dict:
        total = sum(abs(v) for v in feature_weights.values())
        if total == 0: return {}
        normalized = {k: abs(v)/total for k, v in feature_weights.items()}
        return {"trade_id": trade_id, "attribution": normalized}
