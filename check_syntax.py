import ast

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

try:
    ast.parse(content)
    print('Parse OK')
except SyntaxError as e:
    print(f'SyntaxError at line {e.lineno}: {e.msg}')
    lines = content.split('\n')
    for i in range(max(0, e.lineno-5), min(len(content.split('\n')), e.lineno+5)):
        print(f'{i+1}: {repr(lines[i])}')
except Exception as e:
    print(f'Error: {type(e).__name__}: {e}')