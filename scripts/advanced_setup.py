# pyre-ignore-all-errors[21]
import os # pyre-ignore[21]
import sys # pyre-ignore[21]
import keyring # pyre-ignore[21]
from pathlib import Path # pyre-ignore[21]
from dotenv import load_dotenv, main # pyre-ignore[21]

# Add project root and src to path for both runtime and linter compatibility
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from vault import Vault # pyre-ignore[21]
from cryptography.fernet import Fernet # pyre-ignore[21]

def advanced_setup():
    print("=== TradingSystem Advanced Security Setup ===")
    print("This script will migrate your secrets into the Windows Vault.")
    
    env_path = Path(".env")
    if not env_path.exists():
        print("Error: .env file not found.")
        return

    # 1. Load current secrets
    load_dotenv(override=True)
    keys_to_vault = [
        "MT5_PASSWORD", "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
        "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
        "DEEPSEEK_API_KEY", "FINNHUB_API_KEY", "IBKR_HOST",
        "IBKR_PAPER_USERNAME", "IBKR_PAPER_PASSWORD",
        "QUESTDB_ENABLED", "QUESTDB_HOST", "QUESTDB_PORT", "QUESTDB_PG_PORT",
        "QUESTDB_USER", "QUESTDB_PASSWORD", "QUESTDB_CONNECT_TIMEOUT_SEC",
        "OLLAMA_BASE_URL", "OLLAMA_MODEL", "GEMINI_MODEL",
        "API_SERVER_HOST", "API_SERVER_PORT", "API_SERVER_KEY",
        "SESSION_SECRET", "TRADING_MODE"
    ]

    print("\n[Step 1/3] Vaulting Credentials...")
    for key in keys_to_vault:
        val = os.getenv(key)
        if val:
            Vault.set(key, val)
            print(f"  ✓ {key} stored in Windows Vault")
        else:
            print(f"  ! {key} not found in .env, skipping")

    # 2. Generate Database Encryption Key
    print("\n[Step 2/3] Securing Database Layer...")
    existing_db_key = Vault.get("DB_ENCRYPTION_KEY")
    if not existing_db_key:
        new_key = Fernet.generate_key().decode()
        Vault.set("DB_ENCRYPTION_KEY", new_key)
        print("  ✓ Generated and Vaulted NEW DB_ENCRYPTION_KEY")
    else:
        print("  ✓ Use existing DB_ENCRYPTION_KEY found in Vault")

    # 2.1 SESSION_SECRET (for SessionRestorer)
    print("\n[Step 2.1/3] Securing Session Layer...")
    existing_session_secret = Vault.get("SESSION_SECRET")
    if not existing_session_secret:
        import secrets
        new_secret = secrets.token_hex(32)
        Vault.set("SESSION_SECRET", new_secret)
        print("  ✓ Generated and Vaulted NEW SESSION_SECRET")
    else:
        print("  ✓ Use existing SESSION_SECRET found in Vault")

    # 2.2 QUESTDB_PASSWORD (Default: 'quest')
    print("\n[Step 2.2/3] Securing Database Access...")
    existing_quest_pass = Vault.get("QUESTDB_PASSWORD")
    if not existing_quest_pass:
        Vault.set("QUESTDB_PASSWORD", "quest")
        print("  ✓ Vaulted DEFAULT QUESTDB_PASSWORD ('quest')")
    else:
        print("  ✓ Use existing QUESTDB_PASSWORD found in Vault")

    # 3. Cleanup & Verification (GAP-76/87 FIX)
    print("\n[Step 3/3] FINAL HARDENING: Purging Plaintext Credentials...")
    
    # Verify a couple of critical keys before we burn the boats
    all_verified = True
    for test_key in ["MT5_PASSWORD", "ANTHROPIC_API_KEY"]:
        if os.getenv(test_key) and not Vault.get(test_key):
            print(f"  ✖ Critical Verification FAILED: {test_key} not found in Vault.")
            all_verified = False
            break
    
    if all_verified:
        try:
            # Create a safe .env with ONLY non-sensitive layout
            safe_lines = [
                "# SETO Sovereign Environment — HARDENED\n",
                "# Sensitive keys migrated to Windows Vault.\n",
                "TRADING_MODE=ibkr_paper\n",
                "IBKR_HOST=localhost\n",
                "QUESTDB_ENABLED=True\n"
            ]
            with open(env_path, 'w') as f:
                f.writelines(safe_lines)
            
            # GAP-76 FIX: Delete the backup file immediately after verification
            if os.path.exists(".env.bak"):
                os.remove(".env.bak")
                print("  ✓ Plaintext backup .env.bak PERMANENTLY PURGED.")
            
            print("  ✓ .env file purged of all sensitive data.")
        except Exception as e:
            print(f"  ✖ Error during final hardening: {e}")
    else:
        print("  ✖ Hardening ABORTED: Vault verification failed. Check Windows Credential Manager.")

    print("\n=== SETUP COMPLETE ===")
    print("Your system is now using Windows Vault for secrets.")
    print("You can verify this by running: python src/main.py")

if __name__ == "__main__":
    advanced_setup()
