import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()

# Test insert
cursor.execute("""
    INSERT INTO audit_engagements (id, engagement_number, client_name, client_id, audit_type, scope,
                                  start_date, end_date, planned_start, planned_end, status, lead_auditor,
                                  team_members, materiality, risk_assessment, planning_notes, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
""", ('eng_test', 'ENG-TEST', 'Test Client', 'client_001', 'financial', 'Full audit',
      1700000000, None, 1700000000, 1800000000, 'planning', 'John Smith',
      '["Jane Doe"]', 50000.0, '{}', 'Test audit', 1234567890, 1234567890))
conn.commit()
print('Insert successful')

cursor.execute('SELECT id, client_name FROM audit_engagements WHERE id = ?', ('eng_test',))
print(cursor.fetchall())
"