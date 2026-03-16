import sqlite3

conn = sqlite3.connect('model_portfolio.db')
cur = conn.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cur.fetchall()
print('Tables:', tables)

for t in tables:
    name = t[0]
    print(f'\n--- {name} ---')
    cur.execute(f'PRAGMA table_info({name})')
    cols = cur.fetchall()
    for c in cols:
        print(c)
    cur.execute(f'SELECT * FROM {name}')
    rows = cur.fetchall()
    print('DATA:')
    for r in rows:
        print(r)

conn.close()
