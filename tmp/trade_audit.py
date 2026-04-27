import sqlite3
from datetime import datetime

conn = sqlite3.connect('data/trading.db')
c = conn.cursor()

print("=" * 70)
print("TRADE EXECUTION AUDIT")
print("=" * 70)

# 1. Check trades table
print("\n[1] TRADES TABLE (all entries):")
try:
    c.execute("SELECT * FROM trades ORDER BY timestamp DESC LIMIT 20")
    cols = [desc[0] for desc in c.description]
    rows = c.fetchall()
    if rows:
        print(f"  Columns: {cols}")
        for r in rows:
            print(f"  {dict(zip(cols, r))}")
    else:
        print("  *** NO TRADES RECORDED ***")
except Exception as e:
    print(f"  Error: {e}")

# 2. Check signals table
print("\n[2] SIGNALS TABLE (last 20):")
try:
    c.execute("SELECT * FROM signals ORDER BY timestamp DESC LIMIT 20")
    cols = [desc[0] for desc in c.description]
    rows = c.fetchall()
    if rows:
        print(f"  Columns: {cols}")
        for r in rows:
            print(f"  {dict(zip(cols, r))}")
    else:
        print("  *** NO SIGNALS RECORDED ***")
except Exception as e:
    print(f"  Error: {e}")

# 3. Check positions table
print("\n[3] POSITIONS TABLE:")
try:
    c.execute("SELECT * FROM positions ORDER BY rowid DESC LIMIT 10")
    cols = [desc[0] for desc in c.description]
    rows = c.fetchall()
    if rows:
        for r in rows:
            print(f"  {dict(zip(cols, r))}")
    else:
        print("  *** NO POSITIONS RECORDED ***")
except Exception as e:
    print(f"  Error: {e}")

# 4. Check performance_summary
print("\n[4] PERFORMANCE SUMMARY:")
try:
    c.execute("SELECT * FROM performance_summary ORDER BY rowid DESC LIMIT 5")
    cols = [desc[0] for desc in c.description]
    rows = c.fetchall()
    if rows:
        for r in rows:
            print(f"  {dict(zip(cols, r))}")
    else:
        print("  *** NO PERFORMANCE DATA ***")
except Exception as e:
    print(f"  Error: {e}")

# 5. Check system_state for trade-related keys
print("\n[5] SYSTEM STATE (trade-related):")
try:
    c.execute("SELECT key, value FROM system_state")
    for r in c.fetchall():
        print(f"  {r[0]}: {r[1]}")
except Exception as e:
    print(f"  Error: {e}")

# 6. List all tables
print("\n[6] ALL TABLES IN DATABASE:")
c.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
for r in c.fetchall():
    c2 = conn.cursor()
    c2.execute(f"SELECT COUNT(*) FROM [{r[0]}]")
    count = c2.fetchone()[0]
    print(f"  {r[0]}: {count} rows")

conn.close()
