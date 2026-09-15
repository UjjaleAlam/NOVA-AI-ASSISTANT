import sqlite3
import time
import traceback

# Add debug output to fail_task method
import core.multi_agent as multi_agent

# Monkey patch fail_task to add debug output
original_fail_task = core.multi_agent.task_queue.fail_task

def debug_fail_task(self, task_id, failure_reason):
    print(f'DEBUG: fail_task called with task_id={task_id}, failure_reason={failure_reason}')
    conn = sqlite3.connect('database/multi_agent.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id, task_type, payload, priority, status, assigned_agent_id, parent_task_id, depends_on,
               created_at, assigned_at, started_at, completed_at, result, error, retry_count, max_retries, timeout
        FROM task_queue WHERE id = ?
    """, (task_id,))
    row = cursor.fetchone()
    print(f'DEBUG: row = {row}')
    if row:
        task_id_db, task_type, payload, priority, status, assigned_agent_id, parent_task_id, depends_on, \
        created_at, assigned_at, started_at, completed_at, result, existing_error, retry_count, max_retries, timeout = row
        print(f'DEBUG: retry_count={retry_count}, max_retries={max_retries}')
        if retry_count < max_retries:
            print('DEBUG: retry_count < max_retries, will retry')
        else:
            print('DEBUG: retry_count >= max_retries, will move to DLQ')
    conn.close()
    return original_fail_task(self, task_id, failure_reason)

# Monkey patch
import core.multi_agent as multi_agent_module
multi_agent_module.task_queue.fail_task = debug_fail_task.__get__(multi_agent_module.task_queue, multi_agent_module.TaskQueueManager)

# Now test
import sqlite3
import time

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

try:
    print('Calling fail_task (1st failure)...')
    task_queue.fail_task('test_task_dlq_1', 'Test timeout error')
    print('fail_task completed (1st call)')
except Exception as e:
    print('Exception:', e)
    import traceback
    traceback.print_exc()

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