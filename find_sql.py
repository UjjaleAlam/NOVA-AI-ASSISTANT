with open(r'C:\Users\LENOVO\Videos\JARVIS\core\executive_assistant.py', 'r', encoding='utf-8') as f:
    content = f.read()

idx = content.find('cursor.execute("""', content.find('def create_task'))
print('Found at:', idx)

idx2 = content.find('"""', idx + 100)
print('First """ at:', idx2)

idx3 = content.find('"""', idx2 + 3)
print('Second """ at:', idx3)

idx4 = content.find(')', idx3)
print('Closing ) at:', idx4)

print(repr(content[idx:idx4+10]))