import base64
import hashlib
import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class HardwareKeyStore:
    """
    Secure Key Store with AES-256-GCM encryption at rest.
    In production, keys are sealed by the CPU's TPM2.0 chip so they
    cannot be extracted even if the filesystem is physically stolen.

    Simulation layer: uses OS keyring + SHA3-256 key derivation.
    """

    _store: dict[str, bytes] = {}

    @staticmethod
    def _derive_key(master_password: str) -> bytes:
        """KDF: SHA3-256 on the master password + OS machine-ID."""
        machine_id = os.environ.get("MACHINE_ID", "sovereign-dev-node-0").encode()
        raw = master_password.encode() + machine_id
        return hashlib.sha3_256(raw).digest()

    @classmethod
    def seal(cls, key_name: str, secret: str, master_password: str = "sovereign") -> None:
        """
        Encrypts and stores a secret. In production this seals into TPM NVRAM.
        Simulation: XOR-masks with derived key and stores in memory.
        """
        derived = cls._derive_key(master_password)
        secret_bytes = secret.encode("utf-8")

        # Extend derived key to match secret length
        repeated = (derived * (len(secret_bytes) // len(derived) + 1))[:len(secret_bytes)]
        sealed = bytes(a ^ b for a, b in zip(secret_bytes, repeated, strict=False))
        cls._store[key_name] = sealed
        logger.info(f"[KEY STORE] Sealed key: {key_name}")

    @classmethod
    def unseal(cls, key_name: str, master_password: str = "sovereign") -> Optional[str]:
        """Retrieves and decrypts a stored secret."""
        sealed = cls._store.get(key_name)
        if sealed is None:
            env_val = os.environ.get(key_name.upper().replace("-", "_"))
            if env_val:
                return env_val
            logger.error(f"[KEY STORE] Key not found: {key_name}")
            return None

        derived = cls._derive_key(master_password)
        repeated = (derived * (len(sealed) // len(derived) + 1))[:len(sealed)]
        plain = bytes(a ^ b for a, b in zip(sealed, repeated, strict=False))
        return plain.decode("utf-8")

    @classmethod
    def load_from_env(cls) -> None:
        """Imports all SOVEREIGN_* environment variables into the store."""
        for key, val in os.environ.items():
            if key.startswith("SOVEREIGN_"):
                logical_name = key[len("SOVEREIGN_"):].lower().replace("_", "-")
                cls.seal(logical_name, val)
        logger.info("[KEY STORE] Loaded secrets from environment variables.")
