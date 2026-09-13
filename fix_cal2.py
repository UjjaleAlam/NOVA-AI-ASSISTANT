with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the calendar INSERT - add one more ? and one more value
old = 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'
new = 'VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)'

content = content.replace(old, new)

# Also fix the tuple to add None at the end
old_tuple = 'kwargs.get("calendar_source", "local"), time.time(), time.time()))'
new_tuple = 'kwargs.get("calendar_source", "local"), time.time(), time.time(), None))'

content = content.replace(old_tuple, new_tuple)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed calendar INSERT')