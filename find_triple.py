import re

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find('def create_task')
idx2 = content.find('\n    def ', idx + 10)
method = content[idx:idx2] if idx2 != -1 else content[idx:]

for m in re.finditer(r'"""', method):
    print(f'Triple quote at position {m.start()}: {repr(method[max(0,m.start()-20):m.end()+20])}')