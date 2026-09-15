import sqlite3
conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()

# Check triggers
cursor.execute('SELECT * FROM sqlite_master WHERE type="trigger" AND tbl_name="dead_letter_queue"')
triggers = cursor.fetchall()
print('Triggers:', triggers)

# Check foreign keys
cursor.execute('PRAGMA foreign_key_list(dead_letter_queue)')
fks = cursor.fetchall()
print('Foreign keys:', fks)

conn.close()