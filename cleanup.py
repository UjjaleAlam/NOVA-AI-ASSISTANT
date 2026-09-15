import sqlite3

conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM task_queue WHERE id LIKE "test_%"')
cursor.execute('DELETE FROM dead_letter_queue WHERE id LIKE "dlq_%"')
conn.commit()
conn.close()
print('Cleaned up')