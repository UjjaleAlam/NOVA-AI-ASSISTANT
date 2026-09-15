import sqlite3
conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()

# Clear test data
cursor.execute('DELETE FROM task_queue WHERE id LIKE "task_%"')
cursor.execute('DELETE FROM dead_letter_queue WHERE id LIKE "dlq_%"')
conn.commit()

cursor.execute('SELECT COUNT(*) FROM task_queue')
print('Task queue count:', cursor.fetchone()[0])
cursor.execute('SELECT COUNT(*) FROM dead_letter_queue')
print('DLQ count:', cursor.fetchone()[0])

conn.close()