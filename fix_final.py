with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the remaining bracket issues
content = content.replace(
    '             "type": "test", "estimated_hours": 3],\n',
    '             "type": "test", "estimated_hours": 3},\n'
)
content = content.replace(
    '             "type": "document", "estimated_hours": 2],\n',
    '             "type": "document", "estimated_hours": 2},\n'
)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')