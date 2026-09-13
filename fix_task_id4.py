import re

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix task ID generation to be more unique
old = 'task_id = "task_{:08d}".format(int(time.time() * 1000) % 100000000) + "_{:04d}".format(int(time.time() * 10000) % 10000) + "_{:04d}".format(random.randint(0, 9999))'
new = 'task_id = "task_{:08d}".format(int(time.time() * 1000000) % 100000000) + "_{:04d}".format(int(time.time() * 10000) % 10000) + "_{:04d}".format(random.randint(0, 9999)) + "_{:04d}".format(int(time.time() * 100) % 10000)'

content = content.replace(old, new)

# Add random import if not present
if 'import random' not in content:
    content = content.replace('import math', 'import math\nimport random')

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed task ID generation')