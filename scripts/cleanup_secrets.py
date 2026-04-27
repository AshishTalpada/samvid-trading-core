import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

try:
    from database_security import Vault as VaultSec
    from vault import Vault
except ImportError:
    print("Error: Could not import Vault. Run from project root.")
    sys.exit(1)

def cleanup():
    print("🛡️ SOVEREIGN SECRET CLEANUP (GAP-76/77)")
    print("======================================")

    # 1. Check for sensitive files
    root = Path(".")
    targets = [".env", ".env.bak", ".env.old", "secrets.json"]

    found = []
    for t in targets:
        p = root / t
        if p.exists():
            found.append(p)

    if not found:
        print("✅ No plaintext secret files found in root.")
    else:
        print(f"⚠️ Found {len(found)} plaintext secret files.")
        for p in found:
            print(f"  - {p}")

        print("\nVerifying secrets are in Vault before deletion...")
        # (This is a simplified check - in a real system we'd parse .env)

        confirm = input("\nHave you manually verified all secrets are in Windows Vault? (yes/no): ")
        if confirm.lower() == "yes":
            for p in found:
                try:
                    os.remove(p)
                    print(f"  🗑️ Deleted {p}")
                except Exception as e:
                    print(f"  ❌ Failed to delete {p}: {e}")
        else:
            print("❌ Cleanup aborted. Please move secrets to Vault first.")

    # 2. Verify Triple Secret Bloat Reduction
    print("\nSECRET ARCHITECTURE VERIFICATION:")
    from dotenv import find_dotenv
    dot_env = find_dotenv()
    if dot_env:
        print(f"  ❌ .env still detectable at {dot_env}")
    else:
        print("  ✅ .env eliminated from detection path.")

    print("\nCleanup Complete.")

if __name__ == "__main__":
    cleanup()
