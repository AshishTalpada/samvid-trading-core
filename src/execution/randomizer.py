import random

class ExecutionRandomizer:
    def randomize_slice(self, target_slice_size: int, variance: float = 0.2) -> int:
        offset = target_slice_size * variance
        val = target_slice_size + random.uniform(-offset, offset)
        return max(1, int(round(val)))
