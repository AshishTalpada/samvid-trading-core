import logging
from typing import Dict, Optional
logger = logging.getLogger(__name__)

SECTOR_ADAPTER_MAP: Dict[str, str] = {
    "TECH": "adapters/tech_lora.bin",
    "ENERGY": "adapters/energy_lora.bin",
    "MACRO": "adapters/macro_lora.bin",
    "DEFAULT": "adapters/base_lora.bin",
}

class LoRAManager:
    """Manages dynamic LoRA adapter swapping based on ticker sector."""
    def __init__(self):
        self.current_adapter: Optional[str] = None

    def get_adapter_path(self, sector: str) -> str:
        return SECTOR_ADAPTER_MAP.get(sector.upper(), SECTOR_ADAPTER_MAP["DEFAULT"])

    def swap_adapter(self, sector: str) -> bool:
        path = self.get_adapter_path(sector)
        if path == self.current_adapter:
            return False
        logger.info(f"Swapping LoRA adapter to: {path}")
        self.current_adapter = path
        return True
