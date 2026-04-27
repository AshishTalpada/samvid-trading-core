from ib_insync import IB, MarketOrder
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LIQUIDATION")

def total_liquidation():
    ib = IB()
    try:
        logger.info("Connecting to IBKR for Emergency Liquidation...")
        # Using synchronous ib.connect
        ib.connect('127.0.0.1', 7497, clientId=99)
        
        positions = ib.positions()
        if not positions:
            logger.info("No active positions found. Portfolio is already clean.")
            return

        for pos in positions:
            contract = pos.contract
            quantity = pos.position
            side = 'SELL' if quantity > 0 else 'BUY'
            abs_qty = abs(quantity)
            
            logger.info(f"LIQUIDATING: {side} {abs_qty} {contract.symbol}")
            order = MarketOrder(side, abs_qty)
            trade = ib.placeOrder(contract, order)
            
        logger.info("All Liquidation orders sent. Waiting 5s for fills...")
        ib.sleep(5)
        ib.disconnect()
        logger.info("Liquidation Protocol Complete.")
    except Exception as e:
        logger.error(f"Liquidation Failed: {e}")

if __name__ == "__main__":
    total_liquidation()
