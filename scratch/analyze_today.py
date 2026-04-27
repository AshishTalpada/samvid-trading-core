import sqlite3
import os
from datetime import datetime

db_path = "data/trading.db"
if not os.path.exists(db_path):
    print(f"Error: {db_path} not found.")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

today = datetime.now().strftime("%Y-%m-%d")
print(f"--- Analysis for {today} ---")

# 1. Total Trades today
cursor.execute("SELECT instrument, direction, shares, entry_price, pnl_dollars, timestamp FROM trades WHERE timestamp LIKE ?", (f"{today}%",))
trades = cursor.fetchall()
print(f"Total Trades: {len(trades)}")

for t in trades:
    print(f"[{t[5]}] {t[1]} {t[0]} | Qty: {t[2]} | Price: {t[3]} | PnL: ${t[4] if t[4] else 0.0:.2f}")

# 2. System Status
cursor.execute("SELECT key, value FROM system_state WHERE key IN ('system_status', 'mode', 'last_scan');")
states = cursor.fetchall()
print("\n--- System State ---")
for s in states:
    print(f"{s[0]}: {s[1]}")

conn.close()
