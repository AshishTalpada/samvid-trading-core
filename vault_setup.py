import os
import sys
import secrets
import string
import getpass
from pathlib import Path
from dotenv import load_dotenv

# Add src to sys.path to import Vault
sys.path.append(str(Path(__file__).parent / "src"))
try:
    from vault import Vault
except ImportError:
    print("❌ Error: Could not find src/vault.py. Please run this from the project root.")
    sys.exit(1)

def generate_secure_secret(length=48):
    """Generate a high-entropy random string."""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*()_+"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

import json

def import_from_openbb():
    """Import credentials from ~/.openbb_platform/user_settings.json."""
    # Handle Windows home path
    home = Path.home()
    odp_path = home / ".openbb_platform" / "user_settings.json"
    
    if not odp_path.exists():
        return {}

    try:
        with open(odp_path, "r") as f:
            data = json.load(f)
            creds = data.get("credentials", {})
            
            # Map ODP keys to our SENSITIVE_KEYS
            mapping = {
                "fmp_api_key": "FMP_API_KEY",
                "benzinga_api_key": "BENZINGA_API_KEY",
                "tiingo_token": "TIINGO_API_KEY", 
                "intrinio_api_key": "INTRINIO_API_KEY",
                "biztoc_api_key": "BIZTOC_API_KEY",
                "alpha_vantage_api_key": "ALPHA_VANTAGE_API_KEY",
                "polygon_api_key": "POLYGON_API_KEY",
                "nasdaq_api_key": "NASDAQ_API_KEY"
            }
            
            found = {}
            for odp_key, our_key in mapping.items():
                val = creds.get(odp_key)
                if val and val != "REPLACE" and val.strip():
                    found[our_key] = val
            return found
    except Exception as e:
        print(f"⚠️ Warning: Could not read OpenBB settings: {e}")
        return {}

def setup_vault():
    print("\n" + "="*60)
    print("🛡️  SOVEREIGN CREDENTIAL HYDRATION UTILITY (V3.0)")
    print("="*60)
    print("This tool will populate your secure Windows Vault (keyring).")
    print("Keys already in the Vault will NOT be overwritten unless specified.")
    print("-"*60)

    # 1. Attempt to load from .env and OpenBB JSON
    load_dotenv(override=True)
    odp_creds = import_from_openbb()
    
    missing_keys = []
    for key in Vault.SENSITIVE_KEYS:
        if Vault.get(key) is None:
            missing_keys.append(key)
    
    if not missing_keys:
        print("✅ All sensitive keys are already present in the Vault.")
        return

    print(f"Found {len(missing_keys)} missing or blocked keys.")

    # 2. Handle Auto-Generatable Keys
    AUTO_GEN = ["API_SERVER_KEY", "SESSION_SECRET"]
    for key in AUTO_GEN:
        if key in missing_keys:
            secret = generate_secure_secret()
            Vault.set(key, secret)
            print(f"✨ Auto-generated secure value for {key}")
            missing_keys.remove(key)

    # 3. Handle External Keys (Migration from ODP JSON, .env or Prompt)
    for key in missing_keys:
        # Try migration from OpenBB ODP first
        if key in odp_creds:
            print(f"🔄 Importing '{key}' from OpenBB Settings...")
            Vault.set(key, odp_creds[key])
            continue

        # Try migration from .env
        env_val = os.getenv(key)
        if env_val:
            print(f"📦 Migrating '{key}' from .env to Vault...")
            Vault.set(key, env_val)
            continue
        
        # If not anywhere else, we must prompt
        print(f"\n🔑 MISSING: {key}")
        if "PASS" in key or "SECRET" in key or "KEY" in key:
            val = getpass.getpass(f"   Enter value for {key} (hidden): ").strip()
        else:
            val = input(f"   Enter value for {key}: ").strip()
            
        if val:
            Vault.set(key, val)
        else:
            print(f"   ⚠️ Skipping {key}. (System may fail to start or connect).")

    print("\n" + "="*60)
    print("✅ HYDRATION COMPLETE")
    print("="*60)
    print("Next Steps:")
    print("1. If you migrated keys from .env, DELETE THEM from the .env file now.")
    print("2. Run the system: .\\venv\\Scripts\\python.exe src\\main.py")
    print("="*60 + "\n")

if __name__ == "__main__":
    try:
        setup_vault()
    except KeyboardInterrupt:
        print("\n\n🛑 Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        sys.exit(1)
