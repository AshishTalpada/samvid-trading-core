from ib_insync import IB, MarketOrder
import time

def force_liquidate():
    ib = IB()
    try:
        print("Sovereign Shield: Connecting for FORCED LIQUIDATION...")
        # clientId 99 to ensure we don't conflict with main.py
        ib.connect('127.0.0.1', 7497, clientId=99)
        
        positions = ib.positions()
        if not positions:
            print("Sovereign Shield: No positions found to liquidate.")
            return

        print(f"Sovereign Shield: Found {len(positions)} positions. Closing now...")
        for pos in positions:
            contract = pos.contract
            qty = pos.position
            # Determine Action
            action = 'SELL' if qty > 0 else 'BUY'
            abs_qty = abs(qty)
            
            print(f"SHIELD: Executing {action} {abs_qty} {contract.symbol}")
            order = MarketOrder(action, abs_qty)
            ib.placeOrder(contract, order)
            
        print("Sovereign Shield: All orders sent. Waiting 10s for confirmation...")
        time.sleep(10)
        
        # Verify
        remaining = ib.positions()
        if not remaining:
            print("Sovereign Shield: SUCCESS. ALL POSITIONS CLOSED.")
        else:
            print(f"Sovereign Shield: WARNING. {len(remaining)} positions still open. Manual check required.")
            
        ib.disconnect()
    except Exception as e:
        print(f"Sovereign Shield: Liquidation CRITICAL ERROR: {e}")

if __name__ == "__main__":
    force_liquidate()
