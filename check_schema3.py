import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="workpapers"')
result = cursor.fetchone()
if result:
    print(result[0])
conn.close()