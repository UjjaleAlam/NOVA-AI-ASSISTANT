import sqlite3
import time

# Test direct INSERT into dead_letter_queue
conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()

# Clean up
cursor.execute('DELETE FROM dead_letter_queue WHERE id LIKE "dlq_%"')
conn.commit()

# Try direct INSERT with debug
dlq_id = 'dlq_debug_123'
task_id = 'test_task_123'
task_type = 'code_generation'
payload = '{"test": "data"}'
priority = 1
assigned_agent_id = 'test_agent'
parent_task_id = None
depends_on = None
created_at = time.time()
assigned_at = None
started_at = time.time()
completed_at = time.time()
result = None
error = 'Test error'
retry_count = 1
max_retries = 1
timeout = 5.0
failed_at = time.time()
failure_reason = 'Test error'
retry_history = '[]'

print('Attempting direct INSERT...')
try:
    cursor.execute('''
        INSERT INTO dead_letter_queue VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (dlq_id, 'task_123', 'code_generation', '{"test": "data"}', 1, 'test_agent', None, None,
          time.time(), None, time.time(), time.time(), None, 'Test error', 1, 1, 5.0,
          time.time(), 'Test error', '[]'))
    print('Direct INSERT succeeded')
    conn.commit()
except Exception as e:
    print('INSERT failed:', e)
    import traceback
    traceback.print_exc()

# Check if inserted
cursor.execute('SELECT * FROM dead_letter_queue')
rows = cursor.fetchall()
print('DLQ after direct INSERT:')
for row in cursor.fetchall():
    print('  ', row)

conn.close()