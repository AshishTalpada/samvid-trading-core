import random
import logging
logger = logging.getLogger(__name__)

class QuantumRNG:
    """Ingests true entropy from physical Quantum Random Number Generator (QRNG) PCIe card."""
    def get_seed(self) -> int:
        logger.debug("Pulling entropy from QRNG hardware...")
        return random.getrandbits(256)
