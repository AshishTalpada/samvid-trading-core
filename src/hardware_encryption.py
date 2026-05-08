import logging
logger = logging.getLogger(__name__)

class HardwareAESEngine:
    """Interfaces with CPU AES-NI instructions for zero-cost disk encryption."""
    def encrypt(self, data: bytes) -> bytes:
        return data  # Mock

    def decrypt(self, data: bytes) -> bytes:
        return data  # Mock
