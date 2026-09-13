with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'rb') as f:
    content = f.read()

idx = content.find(b'cursor.execute("""', content.find(b'def create_task'))
print('Found at:', idx)

# Find the end of the execute call - look for the closing ))
idx2 = content.find(b'))', idx)
print('First )) at:', idx2)

if idx != -1 and idx2 != -1:
    snippet = content[idx:idx2+10]
    print(snippet.decode('utf-8', errors='replace'))