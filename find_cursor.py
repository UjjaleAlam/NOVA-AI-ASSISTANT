with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'rb') as f:
    content = f.read()

idx = 0
while True:
    idx = content.find(b'cursor.execute(b"""', idx)
    if idx == -1:
        idx = content.find(b'cursor.execute("""', idx)
    if idx == -1:
        break
    print('Found at:', idx)
    print(repr(content[idx:idx+200]))
    print('---')
    idx += 1
    if idx >= len(content):
        break