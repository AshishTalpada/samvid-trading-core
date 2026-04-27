import glob, sqlite3

for f in glob.glob('**/*.db', recursive=True) + glob.glob('*.db'):
    try:
        conn = sqlite3.connect(f)
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if 'ohlcv' in tables:
            cnt = cur.execute('SELECT COUNT(*) FROM ohlcv').fetchone()[0]
            if cnt > 0:
                sym_sample = cur.execute('SELECT DISTINCT symbol FROM ohlcv LIMIT 5').fetchall()
                latest = cur.execute("SELECT MAX(timestamp) FROM ohlcv").fetchone()[0]
                tf = cur.execute("SELECT DISTINCT timeframe FROM ohlcv LIMIT 5").fetchall()
                aapl = cur.execute("SELECT COUNT(*) FROM ohlcv WHERE symbol='AAPL'").fetchone()[0]
                aapl_tf = cur.execute("SELECT COUNT(*) FROM ohlcv WHERE symbol='AAPL' AND timeframe='1m'").fetchone()[0]
                print(f'FOUND: {f}')
                print(f'  rows={cnt}  latest={latest}')
                print(f'  timeframes={tf}')
                print(f'  symbols={[s[0] for s in sym_sample]}')
                print(f'  AAPL total={aapl}  AAPL timeframe=1m: {aapl_tf}')
        conn.close()
    except Exception as e:
        pass
