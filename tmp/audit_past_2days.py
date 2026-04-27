import sqlite3
from datetime import datetime

def analyze():
    try:
        conn = sqlite3.connect('data/trading.db')
        cursor = conn.cursor()
        
        # Get trades from the last 2 days
        cursor.execute("SELECT pattern, outcome, r_multiple FROM agent_d_trades WHERE recorded_at >= date('now', '-2 days')")
        rows = cursor.fetchall()
        
        total = len(rows)
        wins = len([r for r in rows if r[1] == 'WIN'])
        losses = len([r for r in rows if r[1] == 'LOSS'])
        avg_r = sum([r[2] for r in rows]) / total if total > 0 else 0
        
        print(f"--- Analysis (Last 2 Days) ---")
        print(f"Total Trades: {total}")
        print(f"Wins: {wins}")
        print(f"Losses: {losses}")
        print(f"Win Rate: {(wins/total)*100:.2f}%" if total > 0 else "N/A")
        print(f"Average R: {avg_r:.4f}")
        
        # Breakdown by pattern
        patterns = {}
        for r in rows:
            pat = r[0]
            if pat not in patterns:
                patterns[pat] = {'wins': 0, 'losses': 0, 'total': 0, 'sum_r': 0}
            patterns[pat]['total'] += 1
            patterns[pat]['sum_r'] += r[2]
            if r[1] == 'WIN': patterns[pat]['wins'] += 1
            else: patterns[pat]['losses'] += 1
            
        print("\n--- Pattern Breakdown ---")
        for pat, stat in patterns.items():
            wr = (stat['wins'] / stat['total']) * 100
            ar = stat['sum_r'] / stat['total']
            print(f"{pat:30} | Trades: {stat['total']:3} | WR: {wr:6.2f}% | Avg R: {ar:8.4f}")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    analyze()
