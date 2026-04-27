import sqlite3
import os

db_path = 'data/sovereign_intelligence_75y.db'

if not os.path.exists(db_path):
    print(f"File {db_path} does not exist.")
    exit(1)

conn = sqlite3.connect(db_path)
cur = conn.cursor()

print("Schema of structural_fingerprints:")
cur.execute("PRAGMA table_info(structural_fingerprints)")
for row in cur.fetchall():
    print(row)

print("\nExisting indexes:")
cur.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='structural_fingerprints'")
for row in cur.fetchall():
    print(row)

# Count records
cur.execute("SELECT count(*) FROM structural_fingerprints")
print(f"\nTotal records: {cur.fetchone()[0]}")

conn.close()
