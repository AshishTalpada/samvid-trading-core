import sys, os
sys.path.insert(0, os.path.join(os.getcwd(), "src"))
from quant_signals import RegimeFilter
import sqlite3
import numpy as np

def get_regimes():
    conn = sqlite3.connect('training_data.db')
    c = conn.cursor()
    symbols = ['SPY', 'QQQ', 'IWM']
    results = {}
    
    for s in symbols:
        c.execute("SELECT close FROM ohlcv WHERE symbol=? AND timeframe='1d' ORDER BY timestamp DESC LIMIT 100", (s,))
        rows = c.fetchall()
        if not rows: continue
        p = np.array([r[0] for r in rows][::-1])
        
        rf = RegimeFilter(n_regimes=3)
        rf.fit(p)
        sig = rf.predict(p)
        results[s] = {
            "regime": sig.meta.get("regime", "UNKNOWN"),
            "confidence": round(sig.confidence * 100, 1),
            "score": round(sig.score, 3)
        }
    return results

if __name__ == "__main__":
    print(get_regimes())
