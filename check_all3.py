import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = cursor.fetchall()
for table in tables:
    table_name = table[0]
    print(table_name)
    cursor.execute('PRAGMA table_info({})'.format(table_name))
    for col in cursor.fetchall():
        print('  {}: {}'.format(col[1], col[2]))
    print()
conn.close()