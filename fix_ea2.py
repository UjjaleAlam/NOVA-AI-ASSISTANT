with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    'def create_task(title: str, **kwargs) -> str:\n    return task_mgr.create_task(title, **kwargs)',
    'def create_task(title: str, description: str = "", **kwargs) -> str:\n    return task_mgr.create_task(title, description, **kwargs)'
)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed')