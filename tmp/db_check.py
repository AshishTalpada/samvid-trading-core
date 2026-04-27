import sqlite3
import os
import shutil

def check_sqlite(db_path):
    print(f"Checking SQLite Integrity: {db_path}")
    if not os.path.exists(db_path):
        print(f"SKIPPED: {db_path} does not exist.")
        return
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("PRAGMA integrity_check")
        result = cursor.fetchone()
        print(f"RESULT: {result[0]}")
        conn.close()
    except Exception as e:
        print(f"ERROR: Integrity check failed: {e}")

def check_chroma(db_dir):
    print(f"Checking ChromaDB Availability: {db_dir}")
    if not os.path.exists(db_dir):
        print(f"SKIPPED: {db_dir} does not exist.")
        return
    try:
        import chromadb
        from chromadb.config import Settings
        client = chromadb.PersistentClient(path=db_dir, settings=Settings(allow_reset=True, anonymized_telemetry=False))
        count = client.heartbeat()
        print(f"RESULT: Chroma Online (Heartbeat: {count})")
    except Exception as e:
        print(f"ERROR: Chroma check failed: {e}")

if __name__ == "__main__":
    check_sqlite('c:/Users/talpa/Desktop/System_Beta/TradingSystem/data/trading.db')
    check_chroma('c:/Users/talpa/Desktop/System_Beta/TradingSystem/data/chroma_db')
