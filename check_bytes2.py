with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'rb') as f:
    content = f.read()
idx = content.find(b'def get_sessions')
# Check the exact bytes
print('Bytes around def get_sessions:')
for i, b in enumerate(content[idx-20:idx+80]):
    ch = chr(b) if 32 <= b < 127 else '?'
    print(f'  {i:3}: {b:3} ({ch})')