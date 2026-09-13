with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove the module-level function definitions that should be in the class
# These are defined after the class ends

# Find the end of the class
idx = content.find('class MultiAgentOrchestrator:')
idx2 = content.find('\nclass ', idx + 10)
cls_content = content[idx:idx2] if idx2 != -1 else content[idx:]

# Find where the class ends and module-level functions start
class_end = cls_content.rfind('\n\n') if cls_content.rfind('\n\n') != -1 else len(cls_content)
# Actually, let's find the end of the class by looking for the next 'def ' at module level
lines = cls_content.split('\n')
class_end_idx = 0
for i, line in enumerate(lines):
    if line.startswith('def ') and not line.startswith('    def '):
        class_end_idx = i
        break

# The class methods should be indented with 4 spaces, module-level with 0
# Let's just replace the entire section from the first module-level function to the end

# Find the module-level function definitions
module_funcs_start = content.find('\ndef get_prioritized_tasks(limit: int = 10)')
if module_funcs_start != -1:
    # Replace from there to the end of those functions
    module_funcs_end = content.find('\n\nif __name__ == "__main__":', module_funcs_start)
    if module_funcs_end == -1:
        module_funcs_end = len(content)
    
    # Remove the module-level function definitions
    before = content[:module_funcs_start]
    after = content[module_funcs_end:]
    content = before + after
    
    with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print('Removed module-level function definitions')
else:
    print('Could not find module-level functions')