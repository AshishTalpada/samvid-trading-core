import sys
import asyncio

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from ib_insync import IB

async def check():
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 7497, clientId=99)
        positions = ib.positions()
        active = [p for p in positions if p.position != 0]
        if not active:
            print("FLAT: No open positions found on IBKR.")
        else:
            print(f"FOUND {len(active)} ACTIVE POSITIONS:")
            for p in active:
                print(f" -> {p.contract.symbol}: {p.position} shares")
    except Exception as e:
        print(f"ERROR: {e}")
    finally:
        ib.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
