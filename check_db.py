import sqlite3

conn = sqlite3.connect('data/trading_v4_sim.db')
conn.row_factory = sqlite3.Row
row = conn.execute("SELECT * FROM decision_snapshots LIMIT 1").fetchone()

for k in row.keys():
    print(f"{k}: {row[k]}")
