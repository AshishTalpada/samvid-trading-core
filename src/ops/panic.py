import logging

logger = logging.getLogger(__name__)

class PanicProtocol:
    """Self-destruct protocol: wipes keys and logs on confirmed physical intrusion detection."""
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run

    def execute(self, reason: str) -> bool:
        logger.critical(f"PANIC PROTOCOL TRIGGERED: {reason}")
        if self.dry_run:
            logger.warning("Dry run — no files deleted.")
            return True
        import glob
        import os
        for pattern in ["*.key", "logs/*.log", "cache/*.db"]:
            for f in glob.glob(pattern, recursive=True):
                try:
                    os.remove(f)
                    logger.info(f"Purged: {f}")
                except OSError:
                    pass
        return True
