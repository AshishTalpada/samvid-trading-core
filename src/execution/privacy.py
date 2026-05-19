import logging
import math
import random

logger = logging.getLogger(__name__)


class DifferentialPrivacyObfuscator:
    """
    Injects Laplacian noise into order execution quantities to obfuscate
    institutional intent from High Frequency Market Makers.
    Ensures that the total quantity traded over the day remains mathematically correct,
    but the individual slice sizes appear entirely random to Level 3 data sniffers.
    """

    def __init__(self, epsilon: float = 0.5):
        self.epsilon = epsilon
        self.running_balance = 0

    def generate_twap_slices(self, total_quantity: int, num_slices: int) -> list[int]:
        if num_slices <= 0:
            return []

        base_slice = total_quantity / num_slices
        slices = []

        # Scale of Laplacian noise based on Privacy parameter epsilon
        b = 1.0 / self.epsilon

        for i in range(num_slices - 1):
            # Sample from Laplace distribution: mu = 0, scale = b
            u = random.uniform(-0.5, 0.5)
            noise = -b * math.copysign(1.0, u) * math.log(1.0 - 2.0 * abs(u))

            # Apply noise and ensure realistic bounds
            raw_slice = base_slice + noise + self.running_balance
            actual_slice = max(1, int(round(raw_slice)))

            # Carry over the rounding/noise error so the total sum is perfect
            self.running_balance += int((base_slice - actual_slice))
            slices.append(actual_slice)

        # Final slice absorbs all remaining quantity
        final_slice = total_quantity - sum(slices)
        if final_slice <= 0:
            logger.warning("DP Obfuscator produced negative final slice; adjusting.")
            slices[-1] += final_slice - 1
            final_slice = 1

        slices.append(final_slice)
        return slices
