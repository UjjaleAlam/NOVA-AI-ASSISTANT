import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('PRAGMA table_info(audit_engagements)')
cols = cursor.fetchall()
print(f'Number of columns: {len(cols)}')
for c in cols:
    print(f'  {c[1]}: cid={c[0]}')