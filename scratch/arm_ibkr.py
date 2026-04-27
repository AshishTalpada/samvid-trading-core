import sys
sys.path.insert(0, 'src')
import keyring

SERVICE = 'TradingSystemV3'

# Clear stale TRADING_MODE from keyring so .env takes control
try:
    keyring.delete_password(SERVICE, 'TRADING_MODE')
    print("Cleared stale TRADING_MODE from Windows Keyring")
except Exception:
    print("TRADING_MODE was not in keyring (already clear)")

# Set authoritative values in keyring
keyring.set_password(SERVICE, 'FORCED_PAPER_MODE', 'false')
keyring.set_password(SERVICE, 'TRADING_MODE', 'ibkr_paper')
print("Set FORCED_PAPER_MODE=false in keyring")
print("Set TRADING_MODE=ibkr_paper in keyring")

# Final verification through full config stack
from vault import Vault
from config import FORCED_PAPER_MODE, TRADING_MODE, STARTING_CAPITAL_CAD

print()
print("=== FINAL CONFIGURATION VERIFICATION ===")
print(f"  FORCED_PAPER_MODE : {FORCED_PAPER_MODE}  (should be False)")
print(f"  TRADING_MODE      : {TRADING_MODE}  (should be ibkr_paper)")
print(f"  STARTING_CAPITAL  : ${STARTING_CAPITAL_CAD}  (should be $500.0)")
print(f"  IBKR_PORT         : {Vault.get('IBKR_PORT')}")
print(f"  IBKR_ACCOUNT_ID   : {Vault.get('IBKR_ACCOUNT_ID')}")
print()
if not FORCED_PAPER_MODE and TRADING_MODE == "ibkr_paper":
    print("  IBKR PAPER TRADING: ARMED AND READY")
    print("  ACTION REQUIRED: Start IBKR Gateway on port 7497, then run the system")
else:
    print(f"  WARNING: Expected ibkr_paper, got: {TRADING_MODE} / paper_mode={FORCED_PAPER_MODE}")
