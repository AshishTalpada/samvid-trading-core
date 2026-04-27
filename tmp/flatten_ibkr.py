import sys
import asyncio
import time

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from ib_insync import IB, MarketOrder

async def main():
    print("⚠️ GLOBAL CANCEL & FORCE LIQUIDATION ⚠️")
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 7497, clientId=99)
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        return

    print("Submitting Global Cancel for all working orders...")
    # This cancels all working Stop-Losses and Take-Profits that are locking the shares
    ib.reqGlobalCancel()
    await asyncio.sleep(2.0)  # Wait for broker to process cancellations

    positions = ib.positions()
    active_positions = [p for p in positions if p.position != 0]
    
    if not active_positions:
        print("✅ Account is completely flat!")
        ib.disconnect()
        return

    print(f"🚨 Force Liquidating {len(active_positions)} positions...")
    
    trades = []
    
    for pos in active_positions:
        contract = pos.contract
        action = 'SELL' if pos.position > 0 else 'BUY'
        qty = abs(pos.position)
        
        print(f"-> Routing {action} {qty} for {contract.symbol}...")
        order = MarketOrder(action, qty)
        order.transmit = True
        
        trade = ib.placeOrder(contract, order)
        trades.append(trade)

    print("\n⏳ Orders dispatched. Waiting for exchanges to process...")
    for _ in range(10):
        await asyncio.sleep(1)
        if all(t.isDone() for t in trades):
            break
            
    print("\n📊 Final Status Digest:")
    for t in trades:
        print(f"   {t.contract.symbol}: {t.orderStatus.status}")

    ib.disconnect()

if __name__ == '__main__':
    asyncio.run(main())
