import logging
from typing import Dict

logger = logging.getLogger(__name__)

class CognitivOrchestrator:
    """Balances reasoning load across available GPU devices by free VRAM."""
    def __init__(self, device_vram: Dict[str, float]):
        self.device_vram = dict(device_vram)

    def assign_task(self, task_name: str, required_vram_gb: float) -> Optional[str]:
        for device, free in sorted(self.device_vram.items(), key=lambda x: -x[1]):
            if free >= required_vram_gb:
                self.device_vram[device] -= required_vram_gb
                logger.debug(f"Assigned '{task_name}' to {device}")
                return device
        logger.warning(f"No device has enough VRAM for '{task_name}'")
        return None

    def release_task(self, device: str, vram_gb: float) -> None:
        self.device_vram[device] = self.device_vram.get(device, 0.0) + vram_gb

from typing import Optional
