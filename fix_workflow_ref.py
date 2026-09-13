with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'r', encoding='utf-8') as f:
    content = f.read()

old = '''            if step_type == "task":
                # Create task and wait for completion
                task_queue = task_queue
                task_id = task_queue.add_task('''

new = '''            if step_type == "task":
                # Create task and wait for completion
                task_queue = self.task_queue
                task_id = self.task_queue.add_task('''

content = content.replace(old, new)

with open(r'C:\Users\LENOVO\Videos\JARVIS\core\multi_agent.py', 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed task_queue reference')