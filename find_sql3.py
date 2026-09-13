with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'rb') as f:
    content = f.read()

idx = content.find(b'cursor.execute(b"""', content.find(b'def create_task'))
if idx == -1:
    idx = content.find(b'cursor.execute("""', content.find(b'def create_task'))

print('Found at:', idx)

# Find the end of the execute call
idx2 = content.find(b'conn.commit()', idx)
print('conn.commit at:', idx2)

if idx != -1 and idx2 != -1:
    snippet = content[idx:idx2+20]
    print(snippet.decode('utf-8', errors='replace'))