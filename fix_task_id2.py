with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'task_id = "task_{:08d}".format(int(time.time() * 1000) % 100000000)'
new = 'task_id = "task_{:08d}".format(int(time.time() * 1000000) % 100000000) + "_{:04d}".format(int(time.time() * 10000) % 10000)'

content = content.replace(old, new)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed task ID generation')