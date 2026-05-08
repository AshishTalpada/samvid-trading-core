import random
from typing import Tuple

class OrderObfuscator:
    """Hides true order intentions by randomizing size slices and execution timing."""

    def __init__(self, max_time_jitter_ms: int = 50, max_size_jitter_pct: float = 0.15):
        self.max_time_jitter_ms = max_time_jitter_ms
        self.max_size_jitter_pct = max_size_jitter_pct

    def obfuscate_order(self, target_size: int) -> Tuple[int, float]:
        """
        Applies jitter to order size and timing to prevent pattern detection.
        
        Args:
            target_size: The exact number of shares/contracts intended.
            
        Returns:
            Tuple containing (obfuscated_size, delay_seconds).
        """
        if target_size <= 1:
            return target_size, 0.0

        # Size jitter: +/- max_size_jitter_pct
        jitter_amount = target_size * self.max_size_jitter_pct
        size_offset = random.uniform(-jitter_amount, jitter_amount)
        
        obfuscated_size = int(round(target_size + size_offset))
        obfuscated_size = max(1, obfuscated_size)
        
        # Time jitter
        delay_seconds = random.uniform(0, self.max_time_jitter_ms) / 1000.0
        
        return obfuscated_size, delay_seconds
