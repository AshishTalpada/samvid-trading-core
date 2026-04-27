# pyre-ignore-all-errors[21]
import asyncio  # pyre-ignore[21]
import sys  # pyre-ignore[21]
from pathlib import Path  # pyre-ignore[21]

# Add project root and src to path
_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(_root / "src"))

from ib_insync import IB  # pyre-ignore[21]

from vault import Vault  # pyre-ignore[21]


async def diagnose():
    host = Vault.get("IBKR_HOST", "127.0.0.1")
    port = int(Vault.get("IBKR_PORT", "7497"))
    client_id = int(Vault.get("IBKR_CLIENT_ID", "1"))

    print("--- IBKR Diagnostic ---")
    print(f"Configured Host: {host}")
    print(f"Configured Port: {port}")
    print(f"Configured ClientID: {client_id}")

    ib = IB()
    try:
        print("Attempting one-time connection...")
        await asyncio.wait_for(ib.connectAsync(host, port, clientId=client_id), timeout=10)
        if ib.isConnected():
            print("SUCCESS: Connected to IBKR.")
            print(f"Managed Accounts: {ib.managedAccounts()}")
            ib.disconnect()
        else:
            print("FAILED: Connection returned but isConnected is False.")
    except Exception as e:
        print(f"ERROR: Could not connect: {e}")
        print("\nPossible solutions:")
        print("1. Change IBKR_CLIENT_ID to a higher number (e.g. 10) in your .env/Vault.")
        print("2. Ensure TWS -> API Settings -> 'Allow connections from localhost only' is checked.")
        print("3. Check if you have another instance of this script running.")

if __name__ == "__main__":
    asyncio.run(diagnose())
