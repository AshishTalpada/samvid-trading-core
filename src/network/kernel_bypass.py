import logging
logger = logging.getLogger(__name__)

class KernelBypassAdapter:
    """Interface to Solarflare onload/libvma for bypassing Linux TCP stack."""
    def __init__(self, interface: str = "eth0"):
        self.interface = interface

    def configure_bypass(self) -> bool:
        logger.info(f"Configuring kernel bypass on {self.interface}...")
        return True
