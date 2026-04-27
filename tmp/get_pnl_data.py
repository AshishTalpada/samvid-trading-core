import sqlite3
import json
import sys
import os

sys.path.insert(0, os.path.abspath('.'))
from src.database_security import DatabaseSecurity

conn = sqlite3.connect('data/trading.db')
cursor = conn.cursor()
cursor.execute("SELECT timestamp, pnl_dollars FROM trades WHERE outcome != 'OPEN' AND pnl_dollars IS NOT NULL AND pnl_dollars != '' ORDER BY timestamp")
rows = cursor.fetchall()

res = []
dates = []
cum = 0

for idx, (t, p) in enumerate(rows):
    val = DatabaseSecurity.decrypt_float(p)
    cum += val
    res.append(round(cum, 2))
    dates.append(f"T{idx+1}")

output = {
    "dates": dates,
    "pnl": res
}

with open("tmp/pnl_data.json", "w") as f:
    json.dump(output, f)
