import sqlite3
conn = sqlite3.connect('data/trading.db')
cursor = conn.cursor()
cursor.execute('SELECT symbol, COUNT(*) FROM ohlcv GROUP BY symbol ORDER BY COUNT(*) DESC LIMIT 20')
print(cursor.fetchall())
conn.close()
