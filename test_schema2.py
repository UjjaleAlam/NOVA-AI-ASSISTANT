import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT sql FROM sqlite_master WHERE type="table" AND name="audit_engagements"')
result = cursor.fetchall()
if result:
    print(result[0][0])
else:
    print("Table not found")
conn.close()