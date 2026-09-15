import sqlite3
import time

conn = sqlite3.connect('database/multi_agent.db')
cursor = conn.cursor()

# Clean up
cursor.execute('DELETE FROM dead_letter_queue WHERE id LIKE "dlq_%"')
conn.commit()

# Test INSERT with debug
dlq_id = 'dlq_test_' + str(int(time.time() * 1000))
vals = (dlq_id, 'task_1', 'code_generation', '{"test": "data"}', 1, 'agent_1', None, None, time.time(), None, time.time(), time.time(), None, 'Test error', 1, 1, 5.0, time.time(), 'Test error', '[]')

print('Attempting INSERT...')
try:
    cursor.execute('INSERT INTO dead_letter_queue VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', (dlq_id, 'task_1', 'code_generation', '{"test": "data"}', 1, 'agent_1', None, None, time.time(), None, time.time(), time.time(), None, 'Test error', 1, 1, 5.0, time.time(), 'Test error', '[]'))
    print('INSERT executed')
    print('Rowcount:', cursor.rowcount)
    
    # Check before commit
    cursor.execute('SELECT * FROM dead_letter_queue WHERE id = ?', (dlq_id,))
    row = cursor.fetchone()
    print('Before commit:', row)
    
    conn.commit()
    print('Committed')
    
    # Check after commit
    cursor.execute('SELECT * FROM dead_letter_queue WHERE id = ?', (dlq_id,))
    row = cursor.fetchone()
    print('After commit:', row)
    
    # Check all
    cursor.execute('SELECT * FROM dead_letter_queue')
    rows = cursor.fetchall()
    print('All rows:', len(rows))
    
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()

conn.close()