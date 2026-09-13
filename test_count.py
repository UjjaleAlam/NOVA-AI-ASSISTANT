import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM pragma_table_info("audit_engagements")')
print('Column count:', cursor.fetchone()[0])
conn.close()