import re

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find('def create_task')
idx2 = content.find('\n    def ', idx + 10)
method = content[idx:idx2] if idx2 != -1 else content[idx:]

# Extract the SQL string (between the triple quotes)
sql_start = method.find('"""') + 3
sql_end = method.find('"""', sql_start + 3)
sql = method[sql_start:sql_end]
print('SQL length:', len(sql))
print('SQL:')
print(sql)
print('---')
# Check for unmatched parentheses in SQL
paren = 0
for i, ch in enumerate(sql):
    if ch == '(':
        print(f'  ( at {i}')
    elif ch == ')':
        print(f'  ) at {i}')