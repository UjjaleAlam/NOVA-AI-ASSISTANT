import sqlite3
import time

# Clean up first
conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()
cursor.execute('DELETE FROM task_queue WHERE id LIKE "test_%"')
cursor.execute('DELETE FROM dead_letter_queue WHERE id LIKE "dlq_%"')
conn.commit()

# Insert test task
cursor.execute('''
    INSERT INTO task_queue (id, task_type, payload, priority, status, assigned_agent_id, parent_task_id, depends_on, created_at, max_retries, timeout)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', ('test_task_dlq_1', 'code_generation', '{"test": "data"}', 1, 'pending', None, None, '[]', time.time(), 1, 5.0))
conn.commit()

print('Created test task')

# Check task before fail
cursor.execute('SELECT * FROM task_queue WHERE id = ?', ('test_task_dlq_1',))
row = cursor.fetchone()
print('Task before fail:', row)

# Call fail_task directly
from core.multi_agent import task_queue

try:
    print('Calling fail_task...')
    task_queue.fail_task('test_task_dlq_1', 'Test timeout error')
    print('fail_task completed')
except Exception as e:
    print('Exception in fail_task:', e)
    import traceback
    traceback.print_exc()

# Check dead letter queue
conn2 = sqlite3.connect('database/multi_agent.db')
cursor2 = conn2.cursor()
cursor2.execute('SELECT * FROM dead_letter_queue')
rows = cursor2.fetchall()
print('Dead letter queue after fail_task:')
for row in cursor2.fetchall():
    print('  ', row)

# Check task_queue
cursor2.execute('SELECT * FROM task_queue WHERE id = ?', ('test_task_dlq_1',))
row = cursor2.fetchone()
print('Task queue after fail_task:', row)

conn2.close()