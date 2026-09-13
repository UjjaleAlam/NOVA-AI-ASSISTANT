with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the create_task method
idx = content.find('def create_task')
idx2 = content.find('\n    def ', idx + 10)
method = content[idx:idx2] if idx2 != -1 else content[idx:]

# Count parentheses and quotes in the method
paren = 0
quote_single = 0
quote_double = 0
triple_quote = 0
in_triple = False

for i, ch in enumerate(method):
    if ch == '(':
        paren += 1
    elif ch == ')':
        paren -= 1
    elif ch == '\'':
        if i+2 < len(method) and method[i+1] == '\'' and method[i+2] == '\'':
            if not in_triple:
                in_triple = True
                triple_quote += 1
            else:
                in_triple = False
        else:
            quote_single += 1
    elif ch == '"':
        if i+2 < len(method) and method[i+1] == '"' and method[i+2] == '"':
            if not in_triple:
                in_triple = True
                triple_quote += 1
            else:
                in_triple = False
        else:
            quote_double += 1

print(f'Paren balance: {paren}')
print(f'Single quotes: {quote_single}')
print(f'Double quotes: {quote_double}')
print(f'Triple quotes: {triple_quote}')
print(f'In triple: {in_triple}')