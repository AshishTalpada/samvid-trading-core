import logging

logger = logging.getLogger(__name__)

class ModelQuantizer:
    """Switches model precision between INT8 (fast) and FP32 (accurate) based on trade urgency."""
    def get_precision(self, urgency: str, time_to_open_secs: float) -> str:
        if urgency == "HFT" or time_to_open_secs < 1.0:
            logger.debug("Using INT8 quantization for speed.")
            return "INT8"
        logger.debug("Using FP32 for deep audit mode.")
        return "FP32"
