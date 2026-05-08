import random

class StealthSlicer:
    """Randomizes TWAP/VWAP slice timing and sizing to prevent detection."""
    def __init__(self, num_slices: int = 10, time_variance_pct: float = 0.3):
        self.num_slices = num_slices
        self.time_variance_pct = time_variance_pct

    def generate_slices(self, total_size: int, total_duration_secs: float) -> list[dict]:
        base_size = total_size // self.num_slices
        base_delay = total_duration_secs / self.num_slices
        slices = []
        for _ in range(self.num_slices):
            size_jitter = random.uniform(0.8, 1.2)
            time_jitter = random.uniform(1 - self.time_variance_pct, 1 + self.time_variance_pct)
            slices.append({
                "size": max(1, int(base_size * size_jitter)),
                "delay_secs": base_delay * time_jitter
            })
        return slices
