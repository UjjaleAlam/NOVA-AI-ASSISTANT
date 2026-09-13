import core.audit_agent as aa
aa.init_audit_db()

import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
print(cursor.fetchall())
cursor.execute('PRAGMA table_info(audit_engagements)')
for row in cursor.fetchall():
    print(row)
conn.close()