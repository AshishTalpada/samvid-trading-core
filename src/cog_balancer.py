import logging

logger = logging.getLogger(__name__)

class CognitiveBalancer:
    def allocate(self, current_vix: float, max_gpus: int = 4) -> int:
        if current_vix > 30:
            logger.info("High VIX: Allocating max GPUs for cognitive load.")
            return max_gpus
        return max(1, max_gpus // 2)
