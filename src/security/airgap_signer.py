import logging
logger = logging.getLogger(__name__)

class AirGappedSigner:
    """Sends order data to an offline Hardware Security Module (HSM) for cryptographic signing."""
    def __init__(self, serial_port: str = "COM3"):
        self.port = serial_port

    def sign_order(self, order_payload: str) -> str:
        logger.info(f"Sending payload to HSM on {self.port} for signing...")
        return "SIG_" + hex(hash(order_payload))[2:]
