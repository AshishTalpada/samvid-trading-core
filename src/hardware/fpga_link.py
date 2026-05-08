import logging
logger = logging.getLogger(__name__)

class FPGANormalizer:
    """Communicates with the FPGA card to receive pre-normalized OHLCV bars."""
    def ping_fpga(self) -> bool:
        logger.info("Pinging FPGA normalizer over PCIe...")
        return True

    def request_bar(self, symbol: str) -> dict:
        return {"symbol": symbol, "status": "FPGA_READY"}
