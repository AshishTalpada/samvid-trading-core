from src.database_security import Vault
import os

print(f"IBKR_INTERFACE: {Vault.get('IBKR_INTERFACE', 'gateway')}")
print(f"TWS_PATH: {Vault.get('TWS_PATH', 'C:\\Jts')}")
print(f"IBC_PATH: {Vault.get('IBC_PATH', 'None')}")

tws_path = Vault.get('TWS_PATH', 'C:\\Jts')
ibkr_interface = Vault.get('IBKR_INTERFACE', 'gateway')

version_search_root = tws_path
if ibkr_interface == "gateway" and os.path.exists(os.path.join(tws_path, "ibgateway")):
    version_search_root = os.path.join(tws_path, "ibgateway")

print(f"Version Search Root: {version_search_root}")
if os.path.exists(version_search_root):
    folders = [f for f in os.listdir(version_search_root) if f.isdigit()]
    print(f"Found version folders: {folders}")
else:
    print(f"Version search root does NOT exist: {version_search_root}")
