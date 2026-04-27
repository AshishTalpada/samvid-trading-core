import sqlite3, datetime, os

for dbfile in ['market_data.db', 'trading.db', 'data/trading.db']:
    if not os.path.exists(dbfile):
        print(f'{dbfile}: NOT FOUND')
        continue
    try:
        conn = sqlite3.connect(dbfile)
        cur = conn.cursor()
        tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        print(f'\n=== {dbfile} ===  tables: {tables}')
        if 'ohlcv' in tables:
            # Sample timestamps
            symbols = ['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'GS', 'MA', 'SPY', 'QQQ']
            print(f'Now: {datetime.datetime.now()}')
            for sym in symbols:
                row = cur.execute("SELECT MAX(timestamp), COUNT(*) FROM ohlcv WHERE symbol=?", (sym,)).fetchone()
                ts, cnt = row
                if ts:
                    try:
                        dt = datetime.datetime.fromisoformat(str(ts).replace('Z','').replace('+00:00',''))
                        age = (datetime.datetime.now() - dt).total_seconds() / 60
                        print(f'  {sym:8s}: latest={ts}  age={age:.1f}min  rows={cnt}')
                    except Exception as e:
                        print(f'  {sym:8s}: latest={ts}  parse_err={e}  rows={cnt}')
                else:
                    print(f'  {sym:8s}: NO ROWS')
        conn.close()
    except Exception as e:
        print(f'{dbfile}: ERROR {e}')

# Also check timeframe column values
for dbfile in ['market_data.db']:
    if not os.path.exists(dbfile):
        continue
    conn = sqlite3.connect(dbfile)
    cur = conn.cursor()
    tables = [r[0] for r in cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    if 'ohlcv' in tables:
        tf_vals = cur.execute("SELECT DISTINCT timeframe FROM ohlcv LIMIT 10").fetchall()
        print(f'\nTimeframe values in ohlcv: {tf_vals}')
        total = cur.execute("SELECT COUNT(*) FROM ohlcv").fetchone()
        print(f'Total ohlcv rows: {total}')
    conn.close()
