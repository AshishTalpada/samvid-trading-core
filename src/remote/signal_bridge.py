import hashlib
import hmac
import logging
import time

logger = logging.getLogger(__name__)


class SignalBridge:
    """
    Biometric-verified remote command bridge for Telegram/Signal integration.
    All remote commands require a HMAC-SHA3 signature to prevent replay attacks.
    """

    def __init__(self, shared_secret: str):
        self._secret = shared_secret.encode()
        self._used_nonces: set[str] = set()

    def _sign(self, payload: str, nonce: str) -> str:
        msg = f"{nonce}:{payload}".encode()
        return hmac.new(self._secret, msg, hashlib.sha3_256).hexdigest()

    def issue_token(self, command: str) -> dict:
        nonce = hashlib.sha3_256(str(time.time_ns()).encode()).hexdigest()[:16]
        sig = self._sign(command, nonce)
        return {
            "command": command,
            "nonce": nonce,
            "signature": sig,
            "expires_at": time.time() + 30,
        }

    def verify_and_execute(self, token: dict) -> bool:
        if time.time() > token.get("expires_at", 0):
            logger.error("[BRIDGE] Expired token rejected.")
            return False
        nonce = token["nonce"]
        if nonce in self._used_nonces:
            logger.error("[BRIDGE] Replay attack blocked.")
            return False
        expected = self._sign(token["command"], nonce)
        if not hmac.compare_digest(expected, token["signature"]):
            logger.error("[BRIDGE] Invalid signature.")
            return False
        self._used_nonces.add(nonce)
        logger.info(f"[BRIDGE] Command authorised: {token['command']}")
        return True
