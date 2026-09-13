import sqlite3
from core.context_engine import get_connection

conn = get_connection()
cursor = conn.cursor()

print("Creating audit_engagements table...")
try:
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_engagements (
            id TEXT PRIMARY KEY,
            engagement_number TEXT UNIQUE NOT NULL,
            client_name TEXT NOT NULL,
            client_id TEXT,
            audit_type TEXT NOT NULL,
            scope TEXT,
            start_date REAL NOT NULL,
            end_date REAL,
            planned_start REAL,
            planned_end REAL,
            status TEXT DEFAULT 'planning',
            lead_auditor TEXT,
            team_members TEXT,
            materiality REAL,
            risk_assessment TEXT,
            planning_notes TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL
        )
    """)
    print("Table created successfully")
except Exception as e:
    print(f"Error: {e}")

conn.commit()
conn.close()

# Check tables
conn = sqlite3.connect('database/audit.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
print(cursor.fetchall())
cursor.execute('PRAGMA table_info(audit_engagements)')
for row in cursor.fetchall():
    print(row)
conn.close()