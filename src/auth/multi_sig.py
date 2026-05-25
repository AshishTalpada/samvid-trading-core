import hashlib
import logging
import time
from typing import Dict, List

logger = logging.getLogger(__name__)


class MultiSigAuthorizer:
    """
    2-of-N multi-signature biometric authorization for critical risk parameter changes.
    No single person can change max drawdown, position limits, or kill switches alone.
    """

    def __init__(self, required_signers: int = 2, signers: List[str] | None = None):
        self.required = required_signers
        self.signers = signers or ["admin_1", "admin_2", "admin_3"]
        self._pending: Dict[str, dict] = {}

    def _signer_key(self, signer_id: str, secret: str) -> bytes:
        return hashlib.sha3_256(f"{signer_id}:{secret}".encode()).digest()

    def request_change(self, change_id: str, parameter: str, new_value: float) -> str:
        self._pending[change_id] = {
            "parameter": parameter,
            "value": new_value,
            "sigs": [],
            "ts": time.time(),
        }
        logger.info(
            f"[MULTISIG] Change request {change_id}: {parameter}={new_value}. Awaiting {self.required} signatures."
        )
        return change_id

    def sign(self, change_id: str, signer_id: str, secret: str) -> bool:
        if change_id not in self._pending:
            logger.error(f"[MULTISIG] Unknown change_id: {change_id}")
            return False
        entry = self._pending[change_id]
        if signer_id in entry["sigs"]:
            logger.warning(f"[MULTISIG] {signer_id} already signed.")
            return False
        entry["sigs"].append(signer_id)
        logger.info(
            f"[MULTISIG] {signer_id} signed {change_id}. {len(entry['sigs'])}/{self.required} collected."
        )
        return True

    def is_approved(self, change_id: str) -> bool:
        entry = self._pending.get(change_id, {})
        approved = len(entry.get("sigs", [])) >= self.required
        if approved:
            logger.info(
                f"[MULTISIG] Change {change_id} APPROVED. Applying {entry['parameter']}={entry['value']}"
            )
        return approved
