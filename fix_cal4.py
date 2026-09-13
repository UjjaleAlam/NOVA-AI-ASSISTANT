with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = 'kwargs.get("calendar_source", "local"), time.time(), time.time(), None))'
new = 'kwargs.get("calendar_source", "local"), time.time(), time.time()))'

content = content.replace(old, new)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed calendar tuple')