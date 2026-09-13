with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'steps = json.loads(workflow[4]) if workflow[4] else []'
new = 'steps = json.loads(workflow[3]) if workflow[3] else []'

content = content.replace(old, new)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed workflow step index')