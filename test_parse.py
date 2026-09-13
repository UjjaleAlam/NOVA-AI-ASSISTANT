import ast

code = """class TaskManager:
    def get_task(self, task_id: str) -> Optional[Dict]:
        conn = get_ea_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM ea_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return self._row_to_task(row)
        return None"""

try:
    ast.parse(code)
    print('Parse OK')
except Exception as e:
    print(f'Error: {e}')