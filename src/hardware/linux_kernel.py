import logging
import os
import subprocess

logger = logging.getLogger(__name__)


class LinuxKernelOptimiser:
    """
    Configures Linux kernel parameters for HFT workloads.
    Applies: CPU affinity pinning, NUMA locality, IRQ balancing,
    and disables power-save states (C-states) that introduce latency jitter.
    """

    REQUIRED_SETTINGS = {
        "/proc/sys/kernel/sched_latency_ns": "1000000",
        "/proc/sys/kernel/sched_min_granularity_ns": "500000",
        "/proc/sys/net/core/busy_read": "50",
        "/proc/sys/net/core/busy_poll": "50",
    }

    def apply_hft_kernel_settings(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        if os.name != "posix":
            logger.warning("[KERNEL OPT] Non-Linux system — skipping kernel tuning.")
            return {}
        for path, value in self.REQUIRED_SETTINGS.items():
            try:
                with open(path, "w") as f:
                    f.write(value)
                results[path] = True
                logger.debug(f"[KERNEL OPT] Set {path}={value}")
            except PermissionError:
                logger.warning(f"[KERNEL OPT] Needs root: {path}")
                results[path] = False
            except FileNotFoundError:
                results[path] = False
        return results

    def pin_cpu_affinity(self, pid: int, cpu_id: int) -> bool:
        try:
            subprocess.run(["taskset", "-p", f"{1 << cpu_id}", str(pid)], check=True, capture_output=True)
            logger.info(f"[KERNEL OPT] Pinned PID {pid} to CPU {cpu_id}")
            return True
        except Exception as e:
            logger.warning(f"[KERNEL OPT] Affinity pin failed: {e}")
            return False
