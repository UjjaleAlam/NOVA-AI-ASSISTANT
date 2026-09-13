import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()

# Check table info
cursor.execute('PRAGMA table_info(audit_engagements)')
cols = cursor.fetchall()
print(f'Number of columns: {len(cols)}')
for c in cols:
    print(f'  {c[1]}: cid={c[0]}')

# Check the SQL being executed
sql = '''
    INSERT INTO audit_engagements (id, engagement_number, client_name, client_id, audit_type, scope,
                                  start_date, end_date, planned_start, planned_end, status, lead_auditor,
                                  team_members, materiality, risk_assessment, planning_notes, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
'''
print(f'Number of placeholders: {sql.count("?")}')

# Count columns in table
cursor.execute('PRAGMA table_info(audit_engagements)')
cols = cursor.fetchall()
print(f'Table has {len(cols)} columns')
for c in cursor.fetchall():
    print(f'  {c[1]}: cid={c[0]}')