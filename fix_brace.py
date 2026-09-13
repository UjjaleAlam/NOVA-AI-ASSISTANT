with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the extra closing brace in the list comprehension
content = content.replace(
    '            "timestamp": r[6], "read": bool(r[6])}\n',
    '            "timestamp": r[6], "read": bool(r[6])}\n'
)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed')