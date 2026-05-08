import numpy as np

class SNNGate:
    """Spike-based neural gate for sub-millisecond binary decisions."""
    def __init__(self, threshold: float = 0.5, decay: float = 0.9):
        self.threshold = threshold
        self.decay = decay
        self.membrane: float = 0.0

    def step(self, input_signal: float) -> bool:
        self.membrane = self.membrane * self.decay + input_signal
        if self.membrane >= self.threshold:
            self.membrane = 0.0
            return True
        return False
