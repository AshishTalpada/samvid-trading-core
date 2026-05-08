import os
import psutil
import logging
logger = logging.getLogger(__name__)

class CPUThreadIsolator:
    """Pins critical execution threads to isolated CPU cores to prevent OS jitter."""
    def pin_current_thread(self, core_id: int) -> bool:
        try:
            p = psutil.Process(os.getpid())
            p.cpu_affinity([core_id])
            logger.info(f"Pinned process {os.getpid()} to CPU core {core_id}")
            return True
        except AttributeError:
            logger.warning("CPU pinning not supported on this OS.")
            return False
