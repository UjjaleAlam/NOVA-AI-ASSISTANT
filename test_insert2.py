import sqlite3
import time

conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()

engagement_id = 'eng_test'
engagement_number = 'ENG-20241219-0001'
client_name = 'Test Client'
client_id = 'client_001'
audit_type = 'financial'
scope = 'Full audit'
start_date = time.time()
end_date = None
planned_start = 1700000000
planned_end = 1800000000
status = 'planning'
lead_auditor = 'John Smith'
team_members = '["Jane Doe"]'
materiality = 50000.0
risk_assessment = '{}'
planning_notes = 'Test audit'
created_at = time.time()
updated_at = time.time()

try:
    cursor.execute("""
        INSERT INTO audit_engagements (id, engagement_number, client_name, client_id, audit_type, scope,
                                      start_date, end_date, planned_start, planned_end, status, lead_auditor,
                                      team_members, materiality, risk_assessment, planning_notes, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (engagement_id, engagement_number, client_name, client_id, audit_type, scope,
          start_date, end_date, planned_start, planned_end, status, lead_auditor,
          team_members, materiality, risk_assessment, planning_notes, created_at, updated_at))
    conn.commit()
    print('Insert successful')
except Exception as e:
    print(f'Error: {e}')
    import traceback
    traceback.print_exc()

conn.close()