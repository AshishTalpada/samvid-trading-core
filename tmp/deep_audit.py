import sqlite3
import os
import pandas as pd
from datetime import datetime

db_path = "data/trading.db"

def analyze_performance():
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        return

    try:
        conn = sqlite3.connect(db_path)
        
        # 1. Overall Account Health
        # Try to get trades data
        df_trades = pd.read_sql_query("SELECT * FROM trades", conn)
        
        if df_trades.empty:
            print("No trade history found in 'trades' table.")
        else:
            # Basic Stats
            total_trades = len(df_trades)
            # Find win/loss columns - might be 'outcome' or 'pnl_dollars'
            # Let's check columns first
            cols = df_trades.columns.tolist()
            
            wins = 0
            losses = 0
            total_pnl = 0.0
            
            if 'outcome' in cols:
                wins = len(df_trades[df_trades['outcome'] == 'WIN'])
                losses = len(df_trades[df_trades['outcome'] == 'LOSS'])
            
            # 2. Drawdown Check
            # Look for recent equity history if available
            try:
                df_equity = pd.read_sql_query("SELECT * FROM equity_history ORDER BY timestamp DESC LIMIT 100", conn)
                if not df_equity.empty:
                    latest_equity = df_equity['equity'].iloc[0]
                    peak_equity = df_equity['equity'].max()
                    current_drawdown = (peak_equity - latest_equity) / peak_equity if peak_equity > 0 else 0
                    print(f"Current Equity: ${latest_equity:.2f}")
                    print(f"Peak Equity: ${peak_equity:.2f}")
                    print(f"Current Drawdown: {current_drawdown:.2%}")
            except:
                pass

            win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
            print(f"--- PERFORMANCE SUMMARY ---")
            print(f"Total Trades: {total_trades}")
            print(f"Win Rate: {win_rate:.2f}% ({wins}W / {losses}L)")
            
            # 3. Agent Consistency (Agent D logs or similar)
            # Check for anomalous recent activity (e.g., many consecutive losses)
            if 'timestamp' in cols:
                df_trades['timestamp'] = pd.to_datetime(df_trades['timestamp'])
                df_trades = df_trades.sort_values('timestamp')
                # Last 10 trades
                recent = df_trades.tail(10)
                recent_wins = len(recent[recent['outcome'] == 'WIN']) if 'outcome' in cols else 0
                print(f"Recent Form (last 10): {recent_wins}W / {10-recent_wins}L")

        # 4. System Stability (Any error logs in the DB?)
        try:
            df_logs = pd.read_sql_query("SELECT level, count(*) as count FROM logs GROUP BY level", conn)
            print("\n--- SYSTEM STABILITY ---")
            for _, row in df_logs.iterrows():
                print(f"{row['level']}: {row['count']} entries")
        except:
            pass

        conn.close()
    except Exception as e:
        print(f"Error during analysis: {e}")

if __name__ == "__main__":
    analyze_performance()
