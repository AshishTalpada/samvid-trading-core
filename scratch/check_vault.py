from vault import Vault
import os
import sys

# Add src to path
sys.path.append(os.getcwd())

key = Vault.get("API_SERVER_KEY")
print(f"VAL:{key if key else 'NONE'}")
