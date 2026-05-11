import logging
import os

import keyring

logger = logging.getLogger(__name__)


class Vault:
    """
    Manages sensitive credentials using the OS-level Credential Manager (keyring).
    Falls back to .env only if the secret is missing from the Vault.
    """

    SERVICE_NAME = "TradingSystemV3"
    _cache: dict[str, str] = {}
    _cache_initialized = False
    SENSITIVE_KEYS = {
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY",
        "FINNHUB_API_KEY",
        "MT5_PASSWORD",
        "QUESTDB_PASSWORD",
        "IBKR_PAPER_PASSWORD",
        "IBKR_PAPER_USERNAME",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "BENZINGA_API_KEY",
        "FMP_API_KEY",
        "TIINGO_API_KEY",
        "BIZTOC_API_KEY",
        "INTRINIO_API_KEY",
        "API_SERVER_KEY",
        "SESSION_SECRET",
        "OPENBB_PAT",
        "MT5_LOGIN",
        "MT5_SERVER",
        "ALPHA_VANTAGE_API_KEY",
        "TELEGRAM_PIN",
        "IBKR_INTERFACE",
        "IBKR_PATH",
        "MT5_PATH",
        "QUESTDB_PATH",
        "POLYGON_API_KEY",
    }

    @staticmethod
    def _is_sensitive(key: str) -> bool:
        """Returns True if the key name matches known sensitive credential patterns."""
        k = key.upper()
        if k in Vault.SENSITIVE_KEYS:
            return True
        # Algorithmic detection for new keys (tokens, secrets, passwords, etc)
        SENSITIVE_PATTERNS = [
            "_KEY",
            "_PASS",
            "_SECRET",
            "_TOKEN",
            "_AUTH",
            "PASSWORD",
            "USERNAME",
            "PIN",
        ]
        return any(p in k for p in SENSITIVE_PATTERNS)

    @staticmethod
    def get(key: str, default: str | None = None) -> str | None:
        """Retrieve a secret from Windows Vault, falling back to environment variables."""
        if key in Vault._cache:
            return Vault._cache[key]

        try:
            # get_password can hang under high load — failures fall through to env.
            val = keyring.get_password(Vault.SERVICE_NAME, key)
            if val is not None:
                final_val = str(val).strip()
                Vault._cache[key] = final_val  # Cache for performance
                return final_val
        except Exception as e:
            logger.debug(f"Vault access error for {key}: {e}")

        # No silent fallback to plaintext .env for sensitive keys — prevents credential leakage.
        if Vault._is_sensitive(key):
            # Strict mode: Warn if sensitive keys are read from .env instead of the vault.
            env_val = os.getenv(key, default)
            if env_val is None:
                logger.error(
                    f"SECURITY BLOCK: Sensitive key '{key}' missing from Vault and .env. Fallback DENIED."
                )
            return env_val

        # Non-sensitive keys (e.g. LOG_LEVEL, PORT) can still use environment variables
        return os.getenv(key, default)

    @staticmethod
    def set(key: str, value: str) -> None:
        """Store a secret in the Windows Vault."""
        try:
            keyring.set_password(Vault.SERVICE_NAME, key, value)
            logger.info(f"✓ Secret '{key}' successfully stored in Windows Vault.")
        except Exception as e:
            logger.error(f"Failed to store secret '{key}' in Vault: {e}")
            raise

    @staticmethod
    def delete(key: str) -> None:
        """Remove a secret from the Windows Vault."""
        try:
            keyring.delete_password(Vault.SERVICE_NAME, key)
        except Exception:
            pass

    @staticmethod
    def get_all_redactable_values() -> list[str]:
        """Retrieve all sensitive values currently in the vault for redaction purposes."""
        values = []
        for key in Vault.SENSITIVE_KEYS:
            val = Vault.get(key, default="")
            if val and len(val) > 3:  # Avoid redacting extremely short strings like '123'
                values.append(val)
        return list(set(values))  # Unique values only


if __name__ == "__main__":
    import sys

    # Basic CLI for managing secrets
    if len(sys.argv) < 2:
        print("Usage: python vault.py [get|set|delete|list] [key] [value]")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    if cmd == "set" and len(sys.argv) == 4:
        Vault.set(sys.argv[2], sys.argv[3])
    elif cmd == "get" and len(sys.argv) == 3:
        print(f"{sys.argv[2]}: {Vault.get(sys.argv[2])}")
    elif cmd == "delete" and len(sys.argv) == 3:
        Vault.delete(sys.argv[2])
        print(f"Deleted {sys.argv[2]}")
    elif cmd == "list":
        print("Available Sensitive Keys:")
        for k in sorted(Vault.SENSITIVE_KEYS):
            exists = "✓" if keyring.get_password(Vault.SERVICE_NAME, k) else " "
            print(f" [{exists}] {k}")
    else:
        print("Invalid command or arguments.")
        print("Invalid command or arguments.")
