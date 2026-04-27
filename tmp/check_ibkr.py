import asyncio
import sys
import os
import logging

sys.path.insert(0, os.path.abspath('.'))
from src.agent_c_ibkr import IBKRConnection # type: ignore
from ib_insync import IB, util

logging.basicConfig(level=logging.ERROR)

async def check():
    ib = IB()
    try:
        await ib.connectAsync('127.0.0.1', 7497, clientId=999)
        conn = IBKRConnection(ib_client=ib)
        print("Connected to IBKR.")
        
        print("\n--- LIVE IBKR POSITIONS ---")
        positions = ib.positions()
        if not positions:
            print("No open positions on IBKR.")
        else:
            for pos in positions:
                print(f"Account: {pos.account} | Symbol: {pos.contract.symbol} | Position: {pos.position} | Avg Cost: ${pos.avgCost:.2f}")

        print("\n--- Account Summary ---")
        summary = ib.accountSummary()
        for item in summary:
            if item.tag in ['NetLiquidation', 'TotalCashValue', 'AvailableFunds', 'GrossPositionValue']:
                print(f"{item.tag}: {item.value} {item.currency}")
                
    except Exception as e:
        print(f"Error connecting: {e}")
    finally:
        ib.disconnect()

if __name__ == "__main__":
    asyncio.run(check())
