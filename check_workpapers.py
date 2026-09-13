import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(workpapers)')
for r in cursor.fetchall():
    print(r)
conn.close()