with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def create_task(title: str, **kwargs) -> str:
    return task_mgr.create_task(title, **kwargs)'''

new = '''def create_task(title: str, description: str = "", **kwargs) -> str:
    return task_mgr.create_task(title, description, **kwargs)'''

content = content.replace(old, new)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('Fixed create_task wrapper')