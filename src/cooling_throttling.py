import logging
import subprocess

logger = logging.getLogger(__name__)

class CoolingThrottler:
    """Hardware safety: Reduce intelligence depth if GPU temp spikes."""
    def __init__(self, temp_threshold: int = 85):
        self.temp_threshold = temp_threshold

    def get_gpu_temp(self) -> int:
        try:
            output = subprocess.check_output(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                encoding="utf-8"
            )
            return int(output.strip())
        except Exception as exc:
            logger.debug("CoolingThrottler: GPU temperature unavailable, using safe fallback: %s", exc)
            return 50 # Default safe fallback

    def adjust_intelligence_depth(self, current_depth: int) -> int:
        temp = self.get_gpu_temp()
        if temp > self.temp_threshold:
            logger.warning(f"GPU Temp {temp}C exceeds {self.temp_threshold}C! Throttling AI context depth.")
            # Halve the depth to reduce thermal load and prevent VRAM crash
            return max(1, current_depth // 2)
        return current_depth
