import sqlite3
conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()

# Check for triggers
cursor.execute('SELECT * FROM sqlite_master WHERE type="trigger" AND tbl_name="dead_letter_queue"')
triggers = cursor.fetchall()
print('Triggers on dead_letter_queue:')
for t in triggers:
    print('  ', t)

# Check table info
cursor.execute('PRAGMA table_info(dead_letter_queue)')
for row in cursor.fetchall():
    print('  ', row)

conn.close()