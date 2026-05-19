import logging
import os
import subprocess

logger = logging.getLogger(__name__)


class RAIDSetupManager:
    """
    Configures and monitors RAID-1 (mirrored) or RAID-10 arrays.
    Ensures no single disk failure causes data loss on critical market data journals.
    Production: uses Linux mdadm.
    """

    def check_raid_health(self, device: str = "/dev/md0") -> dict[str, str]:
        if os.name != "posix":
            return {"status": "UNAVAILABLE", "reason": "Non-Linux system"}
        try:
            result = subprocess.run(
                ["mdadm", "--detail", device], capture_output=True, text=True, timeout=5
            )
            state_line = next((l for l in result.stdout.splitlines() if "State :" in l), "")
            state = state_line.split(":")[-1].strip() if state_line else "UNKNOWN"
            healthy = "clean" in state.lower() or "active" in state.lower()
            if not healthy:
                logger.critical(f"[RAID] {device} unhealthy: {state}")
            return {"device": device, "state": state, "healthy": str(healthy)}
        except FileNotFoundError:
            return {"status": "mdadm_not_found", "device": device}
        except Exception as e:
            logger.error(f"[RAID] Health check failed: {e}")
            return {"status": "ERROR", "error": str(e)}

    def rebuild_array(self, device: str, failed_disk: str) -> bool:
        if os.name != "posix":
            return False
        try:
            subprocess.run(["mdadm", device, "--add", failed_disk], check=True, capture_output=True)
            logger.info(f"[RAID] Rebuild started on {device} with {failed_disk}")
            return True
        except Exception as e:
            logger.error(f"[RAID] Rebuild failed: {e}")
            return False
