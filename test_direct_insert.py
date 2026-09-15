import sqlite3
import time

conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()

cursor.execute('DELETE FROM dead_letter_queue WHERE id LIKE "dlq_%"')
conn.commit()

dlq_id = 'dlq_test_' + str(int(time.time() * 1000))

cursor.execute('INSERT INTO dead_letter_queue VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', 
               ('dlq_test_1', 'task_1', 'code_generation', '{"test": "data"}', 1, 'agent_1', None, None, 
                time.time(), None, time.time(), time.time(), None, 'Test error', 1, 1, 5.0, 
                time.time(), 'Test error', '[]'))
print('Rowcount:', cursor.rowcount)
conn.commit()

cursor.execute('SELECT * FROM dead_letter_queue WHERE id = ?', ('dlq_test_1',))
row = cursor.fetchone()
print('Row:', row)

conn.close()