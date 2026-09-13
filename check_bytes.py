with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'rb') as f:
    content = f.read()
idx = content.find(b'cursor.execute("""')
print('Found at:', idx)
print(repr(content[idx:idx+300]))