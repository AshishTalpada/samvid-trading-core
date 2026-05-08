class SeismicGauges:
    """Detect micro-quakes near oil/gas infrastructure."""
    def calculate_disruption_risk(self, richter_scale: float, distance_km: float) -> float:
        if richter_scale > 4.5 and distance_km < 50:
            return 0.85 # High disruption probability
        return 0.01
