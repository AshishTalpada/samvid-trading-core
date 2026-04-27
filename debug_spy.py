import sqlite3
conn = sqlite3.connect('data/trading.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM ohlcv WHERE symbol = "SPY" ORDER BY timestamp DESC LIMIT 5')
rows = cursor.fetchall()
for r in rows:
    print(r)
conn.close()
