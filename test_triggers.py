import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT sql FROM sqlite_master WHERE type="trigger" AND tbl_name="audit_engagements"')
print(cursor.fetchall())
conn.close()