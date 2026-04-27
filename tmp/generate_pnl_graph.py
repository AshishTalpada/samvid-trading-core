# pyright: reportMissingImports=false
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt  # type: ignore
import sys
import os

# Add root to sys.path to import src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from src.database_security import DatabaseSecurity  # type: ignore
except ImportError:
    from database_security import DatabaseSecurity  # type: ignore

db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'data', 'trading.db'))

try:
    conn = sqlite3.connect(db_path)
    df = pd.read_sql_query("SELECT timestamp, pnl_dollars FROM trades WHERE pnl_dollars IS NOT NULL AND pnl_dollars != ''", conn)
    
    if df.empty:
        print("No completed trades found with PnL data.")
        sys.exit(0)
        
    def decrypt_val(val):
        if not val:
            return 0.0
        # HYBRID RECOVERY: Handle plaintext and encrypted
        try:
            return float(val)
        except (ValueError, TypeError):
            return DatabaseSecurity.decrypt_float(str(val))

    df['pnl'] = df['pnl_dollars'].apply(decrypt_val)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    df['cum_pnl'] = df['pnl'].cumsum()

    plt.figure(figsize=(12, 6))
    plt.plot(df['timestamp'], df['cum_pnl'], marker='o', linestyle='-', color='dodgerblue', linewidth=2)
    plt.fill_between(df['timestamp'], df['cum_pnl'], 0, where=(df['cum_pnl'] >= 0), color='green', alpha=0.3, interpolate=True)
    plt.fill_between(df['timestamp'], df['cum_pnl'], 0, where=(df['cum_pnl'] < 0), color='red', alpha=0.3, interpolate=True)
    
    plt.title('Autonomous Trading System - Cumulative Profit and Loss')
    plt.xlabel('Time')
    plt.ylabel('Cumulative PnL ($)')
    plt.grid(True, linestyle='--', alpha=0.7)
    plt.xticks(rotation=45)
    plt.axhline(0, color='black', linewidth=1)
    plt.tight_layout()

    out_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'pnl_graph.png'))
    plt.savefig(out_path, dpi=300)
    print(f"Graph saved to {out_path}")

except Exception as e:
    print(f"Error generating graph: {e}")
