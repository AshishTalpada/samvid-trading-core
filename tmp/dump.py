import sqlite3
import pandas as pd

conn = sqlite3.connect('data/trading.db')
df = pd.read_sql_query('SELECT * FROM trades', conn)
with open('tmp/trades_summary.txt', 'w') as f:
    f.write(df.to_string(index=False))
