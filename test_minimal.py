import ast

code = """class TaskManager:
    def create_task(self, title: str, description: str = "", **kwargs) -> str:
        task_id = "test"
        return task_id

    def get_task(self, task_id: str) -> Dict:
        conn = None
        return None

    def _row_to_task(self, row) -> Dict:
        return {}

class ProjectManager:
    pass
"""

try:
    ast.parse(code)
    print('Parse OK')
except Exception as e:
    print(f'Error: {e}')