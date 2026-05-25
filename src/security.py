import hashlib
import hmac
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class AESNIEncryptor:
    """AES-256-GCM encryption using hardware AES-NI CPU instructions via cryptography library."""

    def __init__(self, key: bytes | None = None):
        self.key = key or AESGCM.generate_key(256)
        self._aes = AESGCM(self.key)

    def encrypt(self, plaintext: bytes, aad: bytes = b"sovereign") -> bytes:
        nonce = os.urandom(12)
        ct = self._aes.encrypt(nonce, plaintext, aad)
        return nonce + ct

    def decrypt(self, ciphertext: bytes, aad: bytes = b"sovereign") -> bytes:
        nonce, ct = ciphertext[:12], ciphertext[12:]
        return self._aes.decrypt(nonce, ct, aad)

    def hmac_sign(self, data: bytes) -> bytes:
        return hmac.new(self.key, data, hashlib.sha3_256).digest()

    def hmac_verify(self, data: bytes, sig: bytes) -> bool:
        return hmac.compare_digest(self.hmac_sign(data), sig)
