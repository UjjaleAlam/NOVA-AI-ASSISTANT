with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''class WorkflowEngine:
    """Executes defined workflows."""

    def __init__(self):
        self.running_workflows: Dict[str, Dict] = {}

    def create_workflow'''

new = '''class WorkflowEngine:
    """Executes defined workflows."""

    def __init__(self, task_queue=None):
        self.task_queue = task_queue
        self.running_workflows: Dict[str, Dict] = {}

    def create_workflow'''

content = content.replace(old, new)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed WorkflowEngine __init__')