import sqlite3
import time
import traceback

# Test the fail_task method directly with debug output
conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()

cursor.execute('DELETE FROM task_queue WHERE id LIKE "test_%"')
cursor.execute('DELETE FROM dead_letter_queue WHERE id LIKE "dlq_%"')
conn.commit()

cursor.execute('''
    INSERT INTO task_queue (id, task_type, payload, priority, status, assigned_agent_id, parent_task_id, depends_on, created_at, max_retries, timeout)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', ('test_task_dlq_1', 'code_generation', '{"test": "data"}', 1, 'pending', None, None, '[]', __import__('time').time(), 1, 5.0))
conn.commit()

print('Created test task')

cursor.execute('SELECT * FROM task_queue WHERE id = ?', ('test_task_dlq_1',))
row = cursor.fetchone()
print('Before fail:', row)

from core.multi_agent import task_queue

print('Calling fail_task (1st failure)...')
task_queue.fail_task('test_task_dlq_1', 'Test timeout error')
print('fail_task completed (1st call)')

cursor.execute('SELECT * FROM task_queue WHERE id = ?', ('test_task_dlq_1',))
row = cursor.fetchone()
print('After 1st fail:', row)

try:
    task_queue.fail_task('test_task_dlq_1', 'Test timeout error again')
    print('fail_task completed (2nd call)')
except Exception as e:
    print('Exception:', e)
    import traceback
    traceback.print_exc()

cursor.execute('SELECT * FROM task_queue WHERE id = ?', ('test_task_dlq_1',))
row = cursor.fetchone()
print('After 2nd fail:', row)

conn2 = sqlite3.connect('database/multi_agent.db')
cursor2 = conn2.cursor()
cursor2.execute('SELECT * FROM dead_letter_queue')
rows = cursor2.fetchall()
print('DLQ after 2nd fail:')
for row in cursor2.fetchall():
    print('  ', row)

conn2.close()
conn.close()