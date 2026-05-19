import logging
import os
import shutil
from typing import List

logger = logging.getLogger(__name__)


class PhysicalPanicSwitch:
    """
    Self-destruct mechanism linked to a physical tamper seal on the server chassis.
    If intrusion is detected, instantly wipes all decrypted API keys, cryptographic
    logs, and proprietary model weights from memory and disk.
    """

    def __init__(self, secure_paths: List[str]):
        self.secure_paths = secure_paths

    def trigger_wipe(self) -> bool:
        logger.critical("!!! PANIC SWITCH TRIGGERED - PHYSICAL INTRUSION DETECTED !!!")
        logger.critical("INITIATING SECURE WIPE OF PROPRIETARY DATA.")

        success = True
        for path in self.secure_paths:
            try:
                if os.path.exists(path):
                    if os.path.isdir(path):
                        # Overwrite files before deleting
                        for root, _, files in os.walk(path):
                            for f in files:
                                p = os.path.join(root, f)
                                size = os.path.getsize(p)
                                with open(p, "wb") as wipe_file:
                                    wipe_file.write(os.urandom(size))
                        shutil.rmtree(path)
                    else:
                        size = os.path.getsize(path)
                        with open(path, "wb") as wipe_file:
                            wipe_file.write(os.urandom(size))
                        os.remove(path)
                    logger.critical(f"WIPED: {path}")
            except Exception as e:
                logger.error(f"Failed to wipe {path}: {e}")
                success = False

        # Force immediate process termination to clear RAM
        logger.critical("WIPE COMPLETE. TERMINATING PROCESS TO CLEAR RAM.")
        import sys

        sys.exit(99)
        return success
