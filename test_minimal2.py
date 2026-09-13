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

    def update_task(self, task_id: str, **kwargs) -> bool:
        return True

    def get_tasks(self, status: str = None, category: str = None,
                  project_id: str = None, tag: str = None):
        return []

    def complete_task(self, task_id: str) -> bool:
        return True

    def get_overdue_tasks(self):
        return []

    def get_today_tasks(self):
        return []

class ProjectManager:
    pass
"""

try:
    ast.parse(code)
    print('Parse OK')
except Exception as e:
    print(f'Error: {e}')