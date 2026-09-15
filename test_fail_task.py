import sqlite3
import time
from core.multi_agent import task_queue

# Test fail_task directly
conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()

# Create a test task
tid = 'test_task_dlq_123'
cursor.execute('''
    INSERT INTO task_queue (id, task_type, payload, priority, status, assigned_agent_id, parent_task_id, depends_on, created_at, max_retries, timeout)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
''', ('test_task_dlq_1', 'code_generation', '{"test": "data"}', 1, 'pending', None, None, '[]', time.time(), 1, 5.0))
conn.commit()

print('Created test task')

# Call fail_task directly
task_queue.fail_task('test_task_dlq_1', 'Test timeout error')

# Check dead letter queue
cursor.execute('SELECT * FROM dead_letter_queue')
rows = cursor.fetchall()
print('Dead letter queue after fail_task:')
for row in cursor.fetchall():
    print('  ', row)

conn.close()