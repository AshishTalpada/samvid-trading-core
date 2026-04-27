import os
from vault import Vault
from dotenv import load_dotenv

def migrate_to_vault():
    print("🚀 Starting Sovereign Credential Vaulting...")
    
    # Load from .env
    load_dotenv(override=True)
    
    keys_to_vault = Vault.SENSITIVE_KEYS
    found_keys = []

    for key in keys_to_vault:
        val = os.getenv(key)
        if val:
            print(f"Vaulting {key}...")
            Vault.set(key, val)
            found_keys.append(key)
    
    if found_keys:
        print("\n✅ Credentials migrated to Windows Vault.")
        print("⚠️ ACTION REQUIRED: You should now comment out or remove these keys from your .env file.")
        print("The system will now prioritize the secure Vault over plaintext .env files.")
    else:
        print("\n❌ No keys found in .env for migration.")

if __name__ == "__main__":
    migrate_to_vault()
