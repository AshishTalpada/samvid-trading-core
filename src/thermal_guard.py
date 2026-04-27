import asyncio
import logging
import subprocess
import time
from typing import Dict

logger = logging.getLogger(__name__)

class ThermalGuard:
    """
    Sovereign Resource Management (Samvid v1.0-beta-beta-beta Hardened).
    Optimized for Laptop Hardware (Thermal + RAM Safety).
    """

    _cache_temp = 40.0
    _cache_ram = 50.0
    _last_check = 0.0
    _lock = asyncio.Lock()

    _smi_available = None # GAP-163: Cache availability

    @staticmethod
    def get_gpu_temp() -> float:
        """Fetch current GPU temperature via nvidia-smi (Blocking)."""
        # GAP-163 FIX: Check for nvidia-smi existence before calling
        if ThermalGuard._smi_available is False:
            return 40.0

        try:
            import shutil
            if ThermalGuard._smi_available is None:
                ThermalGuard._smi_available = shutil.which("nvidia-smi") is not None
                if not ThermalGuard._smi_available:
                    logger.info("ThermalGuard: nvidia-smi not found. GPU monitoring disabled.")
                    return 40.0

            # GAP-97 FIX: Reduced timeout and more robust parsing
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
                capture_output=True,
                encoding="utf-8",
                timeout=1.5,
                check=True
            )
            return float(res.stdout.strip())
        except subprocess.CalledProcessError as e:
            # GAP-210 FIX: Explicitly log exit code and stderr
            logger.error(f"ThermalGuard: nvidia-smi failed (Exit: {e.returncode}). Stderr: {e.stderr.strip()}")
            ThermalGuard._smi_available = False
            return 40.0
        except Exception as e:
            # GAP-163: If it fails once (e.g. driver issue), assume unavailable for this session
            logger.debug(f"ThermalGuard: General failure calling nvidia-smi: {e}")
            return 40.0

    @staticmethod
    def get_ram_usage() -> float:
        """Fetch current system RAM usage as a percentage (Blocking)."""
        try:
            import psutil
            return psutil.virtual_memory().percent
        except Exception:
            return 50.0

    @classmethod
    async def get_handshake_options(cls, is_critical: bool = False) -> Dict[str, int]:
        """
        Dynamic Intelligence Handshake (Async + Throttled).
        Prevents multiple agents from spawning 'nvidia-smi' simultaneously.
        """
        async with cls._lock:
            now = time.time()
            # Cache results for 30s to prevent I/O saturation
            if now - cls._last_check > 30.0:
                cls._cache_temp = await asyncio.to_thread(cls.get_gpu_temp)
                cls._cache_ram = await asyncio.to_thread(cls.get_ram_usage)
                cls._last_check = now

        temp = cls._cache_temp
        ram = cls._cache_ram

        # ── RESOURCE REGIMES (Samvid v1.0-beta-beta-beta Laptop Optimized) ──

        # 1. SURVIVAL: Total fallback for hardware safety
        if temp >= 82.0 or ram >= 92.0:
             logger.critical(f"🚨 RESOURCE SURVIVAL (Temp: {temp}°C, RAM: {ram}%): Safety Limit HIT. Minimal CPU mode.")
             return {"num_gpu": 0, "num_thread": 1, "keep_alive": 10}

        # 2. STRESS: Significant throttling
        if temp >= 78.0 or ram >= 85.0:
             logger.warning(f"⚠️ RESOURCE STRESS (Temp: {temp}°C, RAM: {ram}%): Throttling LLMs.")
             return {"num_gpu": 0, "num_thread": 2, "keep_alive": 60}

        # 3. SUSTAIN: Strategic split (Keep some GPU to avoid total CPU lockup)
        if temp >= 72.0 or ram >= 78.0:
            if is_critical:
                return {"num_gpu": 20, "num_thread": 4, "keep_alive": -1}
            else:
                return {"num_gpu": 0, "num_thread": 4, "keep_alive": 300}

        # 4. DOMINANCE: Maximum performance
        # GAP-98 FIX: num_gpu 99 is fine as Ollama caps at model layers (usually 28-32)
        return {"num_gpu": 99, "num_thread": 4, "keep_alive": -1}
