import gc
import time
import logging
logger = logging.getLogger(__name__)

class GarbageCollectionTuner:
    """Manages Python GC manually during idle sub-millisecond windows."""
    def force_collect(self) -> None:
        t0 = time.time()
        gc.collect()
        t1 = time.time()
        logger.debug(f"GC forced during idle. Pause: {(t1-t0)*1000:.3f}ms")
