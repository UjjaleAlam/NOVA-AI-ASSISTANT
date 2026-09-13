with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''def create_project(name: str, **kwargs) -> str:
    return project_mgr.create_project(name, **kwargs)'''

new = '''def create_project(name: str, description: str = "", **kwargs) -> str:
    return project_mgr.create_project(name, description, **kwargs)'''

content = content.replace(old, new)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed create_project wrapper')