import asyncio
import logging
from ib_insync import IB, LimitOrder, Stock
import sqlite3
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - NUCLEAR - %(levelname)s - %(message)s')
logger = logging.getLogger("NuclearPanic")

# Pinpoint Reality from latest log bytes
MARKET_SNAPSHOT = {
    "TSLA": 365.85,
    "GOOGL": 332.82,
    "COIN": 186.91,
    "MSFT": 393.67,
    "JPM": 310.58
}

async def main():
    ib = IB()
    try:
        logger.info("☢️ NUCLEAR PANIC: Pinpoint Strike...")
        await ib.connectAsync('127.0.0.1', 7497, clientId=999)
        
        positions = ib.positions()
        for p in positions:
            symbol = p.contract.symbol
            if symbol not in MARKET_SNAPSHOT: continue
            
            contract = p.contract
            qty = p.position
            if qty == 0: continue
            
            await ib.qualifyContractsAsync(contract)
            
            mkt_price = MARKET_SNAPSHOT[symbol]
            action = "SELL" if qty > 0 else "BUY"
            abs_qty = abs(qty)
            
            # Use EXACT market price as Limit
            lmt_price = mkt_price 
            
            logger.info(f"🔥 PINPOINT LIQUIDATION {symbol}: {action} {abs_qty} @ {lmt_price}")
            order = LimitOrder(action, abs_qty, round(lmt_price, 2))
            order.tif = "DAY" # Use DAY to avoid TIF errors
            order.transmit = True
            
            ib.placeOrder(contract, order)
            
        logger.info("☢️ Pinpoint Strike broadcast. Waiting 10s...")
        await asyncio.sleep(10)

        # Final DB Wipe
        db_path = "data/trading.db"
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.execute("UPDATE trades SET outcome = 'LIQUIDATED' WHERE outcome = 'OPEN'")
            conn.commit()
            conn.close()
            logger.info("✅ Database force-synced to LIQUIDATED.")

    except Exception as e:
        logger.error(f"🛑 NUCLEAR CRASH: {e}")
    finally:
        ib.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
