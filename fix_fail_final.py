with open('core/multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the fail_task method
idx = content.find('def fail_task(self, task_id: str, error: str):')
if idx >= 0:
    end_idx = content.find('\n    def get_task_status', content.index('def fail_task'))
    if end_idx < 0:
        end_idx = content.find('\n    def ', content.index('def fail_task') + 100)
    
    new_method = '''def fail_task(self, task_id: str, error: str):
        conn = get_ma_connection()
        cursor = conn.cursor()
        # Select all columns needed for dead letter queue
        cursor.execute("""
            SELECT id, task_type, payload, priority, status, assigned_agent_id, parent_task_id, depends_on,
                   created_at, assigned_at, started_at, completed_at, result, error, retry_count, max_retries, timeout
            FROM task_queue WHERE id = ?
        """, (task_id,))
        row = cursor.fetchone()
        if row:
            # Unpack all columns
            task_id_db, task_type, payload, priority, status, assigned_agent_id, parent_task_id, depends_on, \\
            created_at, assigned_at, started_at, completed_at, result, existing_error, retry_count, max_retries, timeout = row
            
            if retry_count < max_retries:
                cursor.execute("UPDATE task_queue SET status = 'pending', error = ?, retry_count = retry_count + 1 WHERE id = ?",
                              (error, task_id))
                conn.commit()
            else:
                # Move to dead letter queue
                dlq_id = f"dlq_{int(time.time() * 1000) % 100000000:08d}"
                cursor.execute("""
                    INSERT INTO dead_letter_queue VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (dlq_id, task_id, task_type, payload, priority, assigned_agent_id, parent_task_id, depends_on,
                      created_at, assigned_at, started_at, completed_at, result, error, retry_count, max_retries, timeout,
                      time.time(), error, "[]"))
                cursor.execute("DELETE FROM task_queue WHERE id = ?", (task_id,))
                conn.commit()
        conn.close()
        
        # Release resources on failure too
        task_info = self.processing.get(task_id)
        if task_info:
            agent_id = task_info.get("agent_id")
            if agent_id:
                registry.release_resources(agent_id)
        
        with self.lock:
            self.processing.pop(task_id, None)

    def get_task_status(self, task_id: str) -> Optional[Dict]:'''

with open('core/multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find('def fail_task(self, task_id: str, error: str):')
if idx >= 0:
    end_idx = content.find('\n    def get_task_status', content.index('def fail_task'))
    if end_idx < 0:
        end_idx = content.find('\n    def ', content.index('def fail_task') + 100)
    
    new_content = content[:idx] + new_method + content[end_idx:]
    with open('core/multi_agent.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Fixed fail_task method')
else:
    print('fail_task method not found')