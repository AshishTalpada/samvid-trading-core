import sqlite3
import os

db_path = "data/trading.db"
conn = sqlite3.connect(db_path)
cur = conn.cursor()
try:
    cur.execute("SELECT instrument, direction, shares, entry_price, stop_price, target_price, r_r_ratio, belief_at_entry FROM trades WHERE instrument='COIN' LIMIT 5")
    rows = cur.fetchall()
    print("COIN Trades Analysis:")
    for r in rows:
        print(f"Instr: {r[0]} | Dir: {r[1]} | Shares: {r[2]} | Entry: {r[3]} | Stop: {r[4]} | Target: {r[5]} | R/R: {r[6]} | Belief: {r[7]}")
except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
