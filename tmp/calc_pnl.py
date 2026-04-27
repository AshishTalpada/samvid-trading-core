import sqlite3
import pandas as pd
from src.database_security import DatabaseSecurity # type: ignore

db_sec = DatabaseSecurity()
conn = sqlite3.connect('data/trading.db')
df = pd.read_sql_query('SELECT instrument, pnl_dollars FROM trades', conn)

print("=== DECRYPTED TRADE PNL ===")
total_pnl = 0.0

for _, row in df.iterrows():
    val = row['pnl_dollars']
    if pd.isna(val) or val is None or not str(val).startswith('gAAAA'):
        continue
    
    try:
        decrypted = db_sec.decrypt(val)
        pnl = float(decrypted)
        total_pnl += pnl
        
        sign = "+" if pnl > 0 else ""
        print(f"{row['instrument']}: {sign}${pnl:.2f}")
    except Exception as e:
        print(f"Failed to decrypt for {row['instrument']}: {e}")

print("===========================")
print(f"TOTAL PNL: ${total_pnl:.2f}")
