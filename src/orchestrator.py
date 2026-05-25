import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class CognitivOrchestrator:
    """
    Balances reasoning load across available GPU devices by monitoring free VRAM.
    Ensures that massive SLM/LLM inference tasks do not OOM the primary GPU
    by shifting non-critical tasks to secondary devices dynamically.
    """

    def __init__(self, device_vram_gb: Dict[str, float]):
        self.device_vram = dict(device_vram_gb)
        self.active_tasks: Dict[str, str] = {}

    def assign_task(self, task_name: str, required_vram_gb: float) -> Optional[str]:
        # Sort devices by most free VRAM
        for device, free in sorted(self.device_vram.items(), key=lambda x: -x[1]):
            if free >= required_vram_gb:
                self.device_vram[device] -= required_vram_gb
                self.active_tasks[task_name] = device
                logger.debug(
                    f"[ORCHESTRATOR] Assigned '{task_name}' to {device} ({free:.1f}GB free)"
                )
                return device

        logger.warning(
            f"[ORCHESTRATOR] OOM WARNING: No device has {required_vram_gb}GB VRAM for '{task_name}'"
        )
        return None

    def release_task(self, task_name: str, vram_gb: float) -> None:
        if task_name in self.active_tasks:
            device = self.active_tasks.pop(task_name)
            self.device_vram[device] = self.device_vram.get(device, 0.0) + vram_gb
            logger.debug(f"[ORCHESTRATOR] Released {vram_gb}GB on {device} from '{task_name}'")
