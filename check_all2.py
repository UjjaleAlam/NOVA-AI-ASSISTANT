import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = cursor.fetchall()
for table in tables:
    print(table[0])
    cursor.execute('PRAGMA table_info({})'.format(table[0]))
    for col in cursor.fetchall():
        print('  {}: {}'.format(col[1], col[2]))
    print()
conn.close()