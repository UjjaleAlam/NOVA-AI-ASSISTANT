import sqlite3
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT team_members, risk_assessment FROM audit_engagements WHERE id = ?', ('eng_64163497',))
result = cursor.fetchone()
if result:
    print(f'team_members: {repr(result[0])}')
    print(f'Type: {type(result[0])}')
    print(f'Bool: {bool(result[0])}')
    if result[0]:
        print(f'Strip: {repr(result[0].strip())}')
    print(f'risk_assessment: {repr(result[1])}')
conn.close()