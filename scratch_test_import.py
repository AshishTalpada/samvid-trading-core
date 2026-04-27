import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))

try:
    from brain import TradingBrain
    print("SUCCESS: TradingBrain imported.")
except Exception as e:
    import traceback
    traceback.print_exc()
