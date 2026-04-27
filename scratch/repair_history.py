import sqlite3
import os
import sys
from datetime import datetime

# Add src to path for imports
sys.path.append(os.path.join(os.getcwd(), 'src'))
from database_security import DatabaseSecurity

# Snapshot of what we knew at liquidation
MARKET_SNAPSHOT = {
    "TSLA": 365.85,
    "GOOGL": 332.82,
    "COIN": 186.91,
    "MSFT": 393.67,
    "JPM": 310.58,
    "SMCI": 27.55,
    "DIA": 485.10,
    "SPY": 693.00,
    "V": 309.50
}

def repair_history():
    db_path = "data/trading.db"
    if not os.path.exists(db_path):
        print("DB not found.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Update Exit Prices and Calculate PnL for the Liquidated Trades
    # Note: exit_price column is NOT encrypted, but pnl_dollars IS.
    cursor.execute("SELECT id, instrument, shares, entry_price FROM trades WHERE outcome='CLOSED' OR outcome='LIQUIDATED'")
    orphans = cursor.fetchall()
    
    for row in orphans:
        tid, symbol, shares, entry = row
        exit_price = MARKET_SNAPSHOT.get(symbol)
        
        # If we already have a record but it's not encrypted (the source of the crash)
        # We need to re-read and re-write correctly.
        
        if exit_price:
            # PnL = (Exit - Entry) * shares 
            pnl = (exit_price - entry) * shares
            
            # ENCRYPT the PnL before writing
            encrypted_pnl = DatabaseSecurity.encrypt_float(pnl)
            
            cursor.execute("""
                UPDATE trades 
                SET exit_price = ?, pnl_dollars = ?, outcome = 'CLOSED' 
                WHERE id = ?
            """, (exit_price, encrypted_pnl, tid))
            print(f"✅ ENCRYPTED & RECORDED: {symbol} | PnL: ${pnl:.2f}")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    repair_history()
