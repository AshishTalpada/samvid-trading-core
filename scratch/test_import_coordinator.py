import sys
import os

# Align path with simulation environment
sys.path.insert(0, os.getcwd())
sys.path.insert(0, os.path.join(os.getcwd(), "src"))

import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

print("DEBUG: Starting import of TradingCoordinator from coordinator...")
try:
    from coordinator import TradingCoordinator
    print("DEBUG: Import SUCCESSFUL")
except Exception as e:
    print(f"DEBUG: Import FAILED with error: {e}")
    import traceback
    traceback.print_exc()
