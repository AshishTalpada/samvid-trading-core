import os
import sys
from pathlib import Path

# Add src to sys.path to import Vault
sys.path.append(str(Path(__file__).parent))
try:
    from vault import Vault
except ImportError:
    print("❌ Error: Could not find vault.py.")
    sys.exit(1)

import getpass
import json


def check_vault_service():
    """GAP-123 FIX: Verify keyring backend is available."""
    import keyring
    backend = keyring.get_keyring()
    if "fail" in str(backend).lower():
         print("❌ CRITICAL: No secure keyring backend found. Secrets cannot be stored safely.")
         sys.exit(1)
    print(f"✓ Keyring service detected: {type(backend).__name__}")

def initialize_vault():
    check_vault_service()
    print("\n🛡️  SOVEREIGN VAULT INITIALIZATION (Hardened)")
    print("-" * 50)

    # Essential keys without default values to avoid leaks
    SENSITIVE_KEYS = [
        "EXEC_SECRET",
        "API_SERVER_KEY",
        "SESSION_SECRET",
        "QUESTDB_PASSWORD",
        "QUESTDB_PATH",
        "TELEGRAM_BOT_TOKEN",
        "TELEGRAM_CHAT_ID",
        "TELEGRAM_PIN",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "POLYGON_API_KEY",
        "ALPHA_VANTAGE_API_KEY",
        "IBKR_PAPER_USERNAME",
        "IBKR_PAPER_PASSWORD",
        "IBKR_INTERFACE",
        "IBKR_PATH",
        "MT5_PATH",
        "MT5_LOGIN",
        "MT5_PASSWORD",
        "MT5_SERVER"
    ]

    # GAP-124: Support Batch Mode via JSON file
    if "--batch" in sys.argv:
        batch_idx = sys.argv.index("--batch") + 1
        if batch_idx < len(sys.argv):
            batch_file = sys.argv[batch_idx]
            if os.path.exists(batch_file):
                try:
                    with open(batch_file, "r") as f:
                        data = json.load(f)
                        for k, v in data.items():
                            Vault.set(k, v)
                            print(f"✓ Batch set: {k}")
                    print("✅ Batch initialization complete.")
                    return
                except Exception as e:
                    print(f"❌ Batch error: {e}")
                    sys.exit(1)

    # Interactive Mode
    print("Press Enter to skip a key or keep existing value.\n")
    for key in SENSITIVE_KEYS:
        existing = Vault.get(key)
        prompt = f"Enter value for {key}"
        if existing:
             # GAP-122 FIX: Prompt before overwrite
             prompt += " (Existing present. Overwrite? [y/N])"
             choice = input(prompt).strip().lower()
             if choice != 'y':
                 continue
             prompt = f"Enter NEW value for {key}"

        # GAP-121 FIX: Use getpass to avoid leaking keys to terminal history
        val = getpass.getpass(f"{prompt}: ").strip()
        if val:
            Vault.set(key, val)
            print(f"✅ '{key}' updated.")
        else:
            if not existing:
                print(f"⚠️  Warning: '{key}' remains uninitialized.")

    print("-" * 50)
    print("✅ Vault Initialization Complete.")

if __name__ == "__main__":
    initialize_vault()
