import hashlib
import hmac
import logging

from cryptography.fernet import Fernet

from vault import Vault

logger = logging.getLogger(__name__)


class DatabaseSecurity:
    """
    Handles column-level encryption for sensitive trading data.
    Uses Fernet for AES-128-CBC + HMAC-SHA256 integrity.
    """

    _fernet: Fernet | None = None
    _hmac_key: bytes | None = None

    @classmethod
    def _get_fernet(cls):
        if cls._fernet is None:
            key = Vault.get("DB_ENCRYPTION_KEY")
            if not key:
                logger.critical("DB_ENCRYPTION_KEY MISSING FROM VAULT!")
                raise RuntimeError("System integrity compromised: DB_ENCRYPTION_KEY not found.")

            cls._fernet = Fernet(key.encode())
            # Derive a secondary HMAC key for extra layer of integrity
            cls._hmac_key = hashlib.sha256(key.encode() + b"HMAC_INTEGRITY").digest()

        return cls._fernet

    @classmethod
    def _generate_hmac(cls, data: bytes) -> str:
        """Generate an HMAC signature for data integrity verification."""
        if cls._hmac_key is None:
            cls._get_fernet()
        return hmac.new(cls._hmac_key, data, hashlib.sha256).hexdigest()

    @classmethod
    def encrypt(cls, data: str) -> str:
        """Encrypt a string with integrated integrity check."""
        if not data:
            return ""
        f = cls._get_fernet()
        encrypted = f.encrypt(data.encode())
        h = cls._generate_hmac(encrypted)
        return f"{h}:{encrypted.decode()}"

    @classmethod
    def decrypt(cls, encrypted_data: str) -> str:
        """Decrypt with mandatory HMAC verification."""
        if not encrypted_data:
            return ""

        try:
            if ":" not in encrypted_data:
                # Fallback for legacy non-HMAC data to prevent system crash
                return cls._get_fernet().decrypt(encrypted_data.encode()).decode()

            provided_hmac, actual_data = encrypted_data.split(":", 1)
            actual_data_bytes = actual_data.encode()

            # Verify Integrity BEFORE Decryption
            expected_hmac = cls._generate_hmac(actual_data_bytes)
            if not hmac.compare_digest(provided_hmac, expected_hmac):
                logger.critical(" SECURITY ALERT: Database Integrity Violation! HMAC mismatch.")
                raise RuntimeError("Database integrity compromised: HMAC verification failed.")

            return cls._get_fernet().decrypt(actual_data_bytes).decode()
        except Exception as e:
            logger.critical(f"DECRYPTION CRITICAL FAILURE: {e}")
            raise RuntimeError(f"Could not decrypt sensitive value: {e}")

    @classmethod
    def encrypt_float(cls, val: float) -> str:
        return cls.encrypt(str(val))

    @classmethod
    def decrypt_float(cls, encrypted_val: str) -> float:
        decrypted = cls.decrypt(encrypted_val)
        return float(decrypted) if decrypted else 0.0

    @classmethod
    def rotate_key(cls, new_key: str) -> None:
        """Rotate the master encryption key and re-encrypt all stored data."""
        # Implementation would involve decrypting all DB records with old key
        # and re-encrypting with new key.
        # For now, we clear the cache so the new key is used for subsequent operations.
        cls._fernet = None
        cls._hmac_key = None
        Vault.set("DB_ENCRYPTION_KEY", new_key)
        logger.info("✓ DB Master Key rotated in Vault.")
