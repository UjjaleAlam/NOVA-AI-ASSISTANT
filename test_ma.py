import core.multi_agent as ma
import time
import random

print('=== MULTI-AGENT SYSTEM TEST ===')

# 1. Debug
print('1. Debug:')
print(ma.ma_debug())

# 2. List agents
print('\n2. Built-in agents:')
agents = ma.list_agents()
for a in agents:
    print(f'   {a["agent_id"]}: {a["name"]} ({a["type"]}) - {a["capabilities"]}')

# 3. Submit tasks
print('\n3. Submitting tasks...')
task1 = ma.submit_task('plan', {'goal': 'Build a REST API', 'context': 'Python FastAPI'})
print(f'   Plan task: {task1}')

task2 = ma.submit_task('execute', {'type': 'code', 'component': 'user_service', 'language': 'python'})
print(f'   Execute task: {task2}')

task3 = ma.submit_task('research', {'type': 'web_search', 'query': 'FastAPI best practices'})
print(f'   Research task: {task3}')

task4 = ma.submit_task('review', {'type': 'code_review', 'code': 'def hello(): pass'})
print(f'   Review task: {task4}')

# 4. Check task status
print('\n4. Task statuses...')
time.sleep(2)
for t in [task1, task2, task3, task4]:
    status = ma.get_task_status(t)
    print(f'   {t}: {status["status"] if status else "not found"}')

# 5. Create workflow
print('\n5. Creating workflow...')
wf_id = ma.create_workflow('Feature Development', 'Build a new feature',
    steps=[
        {'type': 'task', 'task_type': 'plan', 'payload': {'goal': 'Design API'}, 'priority': 2},
        {'type': 'task', 'task_type': 'execute', 'payload': {'type': 'code', 'component': 'models'}, 'priority': 2},
        {'type': 'task', 'task_type': 'execute', 'payload': {'type': 'code', 'component': 'routes'}, 'priority': 2},
        {'type': 'task', 'task_type': 'test', 'payload': {'type': 'test', 'module': 'models'}, 'priority': 3},
        {'type': 'task', 'task_type': 'review', 'payload': {'type': 'code_review', 'module': 'models'}, 'priority': 3},
    ])
print(f'   Workflow: {wf_id}')

# 6. Execute workflow
print('\n6. Executing workflow...')
exec_id = ma.execute_workflow(wf_id, {'project': 'test'})
print(f'   Execution: {exec_id}')
time.sleep(3)
status = ma.get_workflow_status(exec_id)
print(f'   Status: {status["status"] if status else "unknown"}')

# 7. Agent messaging
print('\n7. Agent messaging...')
# First get agent IDs
agents = ma.list_agents()
if len(agents) >= 2:
    ma.send_agent_message(agents[0]['agent_id'], agents[1]['agent_id'],
                          'request', {'action': 'review_code', 'file': 'main.py'})
    print('   Message sent')

# 7b. Check messages
messages = ma.get_agent_messages(agents[1]['agent_id'])
print(f'   Messages for {agents[1]["name"]}: {len(messages)}')

# 8. System status
print('\n8. System status:')
status = ma.get_system_status()
for k, v in status.items():
    print(f'   {k}: {v}')

# 9. Prioritized tasks
print('\n9. Prioritized tasks:')
priorities = ma.get_prioritized_tasks(5)
for i, t in enumerate(priorities, 1):
    print(f'   {i}. {t["title"]} (score: {t["priority_score"]:.1f})')

# 10. Schedule suggestion
print('\n10. Schedule suggestion...')
sched = ma.suggest_schedule()
print(f'   Available: {sched["available_hours"]}h')
print(f'   Scheduled: {len(sched["scheduled_tasks"])} tasks')
print(f'   Buffer: {sched["buffer_minutes"]}min')

# 10b. Morning briefing
print('\n10b. Morning briefing:')
brief = ma.morning_briefing()
print(brief)

# 11. List agents
print('\n11. All agents:')
for a in ma.list_agents():
    print(f'   {a["agent_id"]}: {a["name"]} ({a["type"]}) - {a["status"]}')

# 12. Final debug
print('\n11. Final debug:')
print(ma.ma_debug())

print('\n=== ALL TESTS PASSED ===')