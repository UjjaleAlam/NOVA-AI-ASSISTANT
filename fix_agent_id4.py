with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'self.agent_id = f"agent_{int(time.time() * 1000) % 100000000:08d}"'
new = 'self.agent_id = "agent_{:08d}_{:04d}_{:04d}".format(int(time.time() * 1000000) % 100000000, int(time.time() * 10000) % 10000, random.randint(0, 9999))'

content = content.replace(old, new)

if 'import random' not in content:
    content = content.replace('import math', 'import math\nimport random')

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed agent ID generation')