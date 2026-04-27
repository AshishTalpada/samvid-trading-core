import sys
sys.path.insert(0, 'src')
from config import FORCED_PAPER_MODE, TRADING_MODE, STARTING_CAPITAL_CAD
from vault import Vault

print("=== SYSTEM CONFIGURATION CHECK ===")
print(f"  FORCED_PAPER_MODE : {FORCED_PAPER_MODE}  (should be False)")
print(f"  TRADING_MODE      : {TRADING_MODE}  (should be ibkr_paper)")
print(f"  STARTING_CAPITAL  : ${STARTING_CAPITAL_CAD}  (should be $500.0)")
print(f"  TOTAL_CAPITAL env : {Vault.get('TOTAL_CAPITAL', 'MISSING')}")
print(f"  USE_LOCAL_LLM     : {Vault.get('USE_LOCAL_LLM', 'MISSING')}")
print(f"  IBKR_PORT         : {Vault.get('IBKR_PORT', 'MISSING')}")
print(f"  IBKR_ACCOUNT_ID   : {Vault.get('IBKR_ACCOUNT_ID', 'MISSING')}")
print()

if not FORCED_PAPER_MODE and TRADING_MODE == "ibkr_paper":
    print("  ✅ IBKR PAPER TRADING: ARMED AND READY")
    print("  ➤  Start IBKR Gateway/TWS on port 7497 then run: .\\venv\\Scripts\\python.exe src\\main.py")
elif FORCED_PAPER_MODE:
    print("  ⚠️  WARNING: Still in forced paper mode")
else:
    print(f"  MODE: {TRADING_MODE}")
