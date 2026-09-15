import sqlite3
conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM pragma_table_info("dead_letter_queue")')
count = cursor.fetchone()[0]
print('Column count:', count)
cursor.execute('PRAGMA table_info(dead_letter_queue)')
for row in cursor.fetchall():
    print('  cid=' + str(row[0]) + ', name=' + row[1] + ', type=' + row[2])
conn.close()