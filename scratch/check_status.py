import sqlite3

conn = sqlite3.connect('data/trading.db')
cursor = conn.cursor()
cursor.execute("PRAGMA table_info(system_events)")
cols = cursor.fetchall()
print("Columns in system_events:", [c[1] for c in cols])

# Check positions/performance
cursor.execute("SELECT COUNT(*) FROM positions")
print("Open Positions:", cursor.fetchone()[0])

cursor.execute("SELECT value FROM system_state WHERE key='peak_equity'")
peak = cursor.fetchone()
print("Peak Equity:", peak[0] if peak else "N/A")

conn.close()
