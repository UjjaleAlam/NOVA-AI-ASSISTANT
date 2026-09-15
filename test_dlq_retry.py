import sqlite3

# Test DLQ with retries
conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()

# Clean up
cursor.execute('DELETE FROM task_queue WHERE id LIKE "test_%"')
cursor.execute('DELETE FROM dead_letter_queue WHERE id LIKE "dlq_%"')
conn.commit()

# Create test task
cursor.execute('''
    INSERT INTO task_queue (id, task_type, payload, priority, status, assigned_agent_id, parent_task_id, depends_on, created_at, max_retries, timeout)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', ('test_task_dlq_1', 'code_generation', '{"test": "data"}', 1, 'pending', None, None, '[]', __import__('time').time(), 1, 5.0))
conn.commit()

print('Created test task')

# Check task before fail
cursor.execute('SELECT * FROM task_queue WHERE id = ?', ('test_task_dlq_1',))
row = cursor.fetchone()
print('Task before fail:', row)

# Call fail_task directly
from core.multi_agent import task_queue

try:
    print('Calling fail_task (1st failure)...')
    task_queue.fail_task('test_task_dlq_1', 'Test timeout error')
    print('fail_task completed (1st call)')
except Exception as e:
    print('Exception in fail_task:', e)
    import traceback
    traceback.print_exc()

# Check task status after first failure
cursor.execute('SELECT * FROM task_queue WHERE id = ?', ('test_task_dlq_1',))
row = cursor.fetchone()
print('Task after 1st fail:', row)

# Second failure - should move to DLQ
try:
    print('Calling fail_task (2nd failure)...')
    task_queue.fail_task('test_task_dlq_1', 'Test timeout error again')
    print('fail_task completed (2nd call)')
except Exception as e:
    print('Exception in fail_task:', e)
    import traceback
    traceback.print_exc()

# Check task queue status
cursor.execute('SELECT * FROM task_queue WHERE id = ?', ('test_task_dlq_1',))
row = cursor.fetchone()
print('Task after 2nd fail:', row)

# Check dead letter queue
conn2 = sqlite3.connect('database/multi_agent.db')
cursor2 = conn2.cursor()
cursor2.execute('SELECT * FROM dead_letter_queue')
rows = cursor2.fetchall()
print('Dead letter queue after 2nd fail:')
for row in cursor2.fetchall():
    print('  ', row)

conn2.close()