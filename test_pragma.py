import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT * FROM pragma_table_info("audit_engagements")')
for r in cursor.fetchall():
    print(r)
conn.close()