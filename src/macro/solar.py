class SolarPrediction:
    """Reduce risk on satellite data during solar flares."""
    def adjust_satellite_trust(self, x_ray_flux: float) -> float:
        # X-class flare threshold
        if x_ray_flux > 1e-4:
            return 0.1 # Don't trust satellite downlinks
        return 1.0
