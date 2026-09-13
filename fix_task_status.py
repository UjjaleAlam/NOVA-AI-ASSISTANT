import re

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the get_task_status method column indices
old = '''            return {\n                "id": row[0], "task_type": row[2], "payload": json.loads(row[3]),\n                "priority": row[4], "status": row[5], "assigned_agent": row[6],\n                "parent_task_id": row[8], "result": json.loads(row[13]) if row[13] else None,\n                "error": row[14]\n            }'''

new = '''            return {\n                "id": row[0], "task_type": row[1], "payload": json.loads(row[2]),\n                "priority": row[3], "status": row[4], "assigned_agent": row[5],\n                "parent_task_id": row[7], "result": json.loads(row[12]) if row[12] else None,\n                "error": row[13]\n            }'''

content = content.replace(old, new)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed get_task_status column indices')