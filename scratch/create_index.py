import sqlite3
import os
import time

db_path = 'data/sovereign_intelligence_75y.db'

if not os.path.exists(db_path):
    print(f"File {db_path} does not exist.")
    exit(1)

print(f"Starting index creation on {db_path} (101M records)... This may take a while.")
start_time = time.time()

conn = sqlite3.connect(db_path)
conn.execute("PRAGMA journal_mode=WAL;")
conn.execute("PRAGMA synchronous=OFF;")

# Create index on pattern_type
try:
    conn.execute("CREATE INDEX IF NOT EXISTS idx_pattern_type ON structural_fingerprints(pattern_type);")
    conn.commit()
    print(f"Index idx_pattern_type created successfully in {time.time() - start_time:.2f} seconds.")
except Exception as e:
    print(f"Error creating index: {e}")

conn.close()
