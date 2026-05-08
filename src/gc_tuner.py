import gc
import logging

logger = logging.getLogger(__name__)


class GarbageCollectorTuner:
    """
    Tunes Python's garbage collector for low-latency HFT execution.
    Disables generational GC during the quorum cycle to prevent 50-200ms pauses.
    Re-enables after execution. Critical: a GC pause during order submission = missed fill.
    """

    def __init__(self):
        self._original_thresholds = gc.get_threshold()
        self._gc_was_enabled = gc.isenabled()

    def enter_critical_section(self) -> None:
        gc.disable()
        logger.debug("[GC TUNER] GC disabled — entering critical execution section")

    def exit_critical_section(self) -> None:
        if self._gc_was_enabled:
            gc.enable()
        logger.debug("[GC TUNER] GC re-enabled — exiting critical section")

    def tune_for_hft(self) -> None:
        # Raise thresholds: collect gen0 every 2000 allocs (default=700), gen1/2 rarely
        gc.set_threshold(2000, 20, 10)
        logger.info(f"[GC TUNER] Thresholds set to {gc.get_threshold()} (was {self._original_thresholds})")

    def force_collect_non_critical(self) -> int:
        before = gc.get_count()
        collected = gc.collect(2)
        logger.debug(f"[GC TUNER] Forced full GC: collected {collected} objects")
        return collected

    def get_stats(self) -> dict:
        return {"threshold": gc.get_threshold(), "counts": gc.get_count(), "enabled": gc.isenabled()}
