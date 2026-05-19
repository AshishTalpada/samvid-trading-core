import hashlib
import logging
import platform

logger = logging.getLogger(__name__)


class HardwareAuditor:
    """
    Verifies hardware authenticity and system integrity.
    In production: reads TPM2.0 Platform Configuration Registers (PCRs) to detect tampering.
    Simulation: generates a deterministic hardware fingerprint from CPU/OS metadata.
    """

    def fingerprint(self) -> str:
        raw = f"{platform.processor()}|{platform.machine()}|{platform.node()}"
        return hashlib.sha3_256(raw.encode()).hexdigest()

    def verify_integrity(self, expected_fingerprint: str) -> bool:
        current = self.fingerprint()
        match = current == expected_fingerprint
        if not match:
            logger.critical(
                f"[HW AUDIT] Fingerprint mismatch! Expected={expected_fingerprint[:16]}... Got={current[:16]}..."
            )
        return match

    def audit_report(self) -> dict:
        return {
            "cpu": platform.processor(),
            "arch": platform.machine(),
            "os": platform.system(),
            "fingerprint": self.fingerprint()[:16] + "...",
        }
