import sqlite3
import os

db_path = "data/trading.db"
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    # Convert all OPEN trades to negative shares (assuming user is primarily shorting in this session)
    conn.execute("UPDATE trades SET shares = -1 * ABS(shares) WHERE outcome='OPEN'")
    conn.commit()
    print(f"✅ Corrected {conn.total_changes} trades to SHORT (negative shares).")
    conn.close()
else:
    print("DB not found")
