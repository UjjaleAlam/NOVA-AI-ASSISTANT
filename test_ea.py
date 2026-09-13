import core.executive_assistant as ea
import time
from datetime import datetime, timedelta

print('=== EXECUTIVE ASSISTANT AGENT TEST ===')

# 1. Debug
print('1. Debug:')
print(ea.ea_debug())

# 2. Create tasks
print()
print('2. Creating tasks...')
now = time.time()
t1 = ea.create_task('Finish Q4 report', 'Complete financial summary', 
                     priority=1, category='work', due_date=now + 86400,
                     estimated_hours=3, tags=['finance', 'urgent'])
t2 = ea.create_task('Team meeting prep', 'Prepare slides', 
                     priority=2, category='work', due_date=now + 43200,
                     estimated_hours=1.5, tags=['meeting'])
t3 = ea.create_task('Exercise', '30 min cardio', 
                     priority=3, category='health', due_date=now + 86400,
                     estimated_hours=0.5, tags=['habit'])
t4 = ea.create_task('Learn Python async', 'Complete tutorial', 
                     priority=4, category='learning', due_date=now + 604800,
                     estimated_hours=4, tags=['python'])
print(f'   Tasks: {t1}, {t2}, {t3}, {t4}')

# 3. Create project
print()
print('3. Creating project...')
proj = ea.create_project('Q4 Launch', 'Product launch preparation',
                         category='work', priority=1,
                         target_date=now + 86400*30, budget=50000,
                         tags=['launch', 'q4'])
print(f'   Project: {proj}')

# 4. Add tasks to project
print()
print('4. Adding tasks to project...')
ea.update_task(t1, project_id=proj)
ea.update_task(t2, project_id=proj)
print('   Tasks assigned to project')

# 5. Calendar events
print()
print('5. Calendar events...')
meeting = ea.create_event('Team standup', now + 3600, now + 5400,
                         event_type='meeting', location='Conference Room A',
                         attendees=['alice@co.com', 'bob@co.com'])
focus = ea.create_event('Deep work - Report', now + 7200, now + 14400,
                       event_type='focus', location='Home office')
print(f'   Events: {meeting}, {focus}')

# 6. Decision
print()
print('6. Decision log...')
dec = ea.create_decision('Choose cloud provider', 
                        'Select between AWS, GCP, Azure for new project',
                        context='Need to decide by Friday',
                        options=[{'option': 'AWS', 'pros': ['mature', 'services'], 'cons': ['cost']},
                                 {'option': 'GCP', 'pros': ['AI/ML', 'pricing'], 'cons': ['fewer regions']},
                                 {'option': 'Azure', 'pros': ['integration', 'hybrid'], 'cons': ['complexity']}],
                        decision_type='strategic', impact_scope='team',
                        impact_level=3, confidence=0.7)
print(f'   Decision: {dec}')

# Make decision
ea.make_decision(dec, 'GCP', 'Best ML/AI services and competitive pricing for our use case')
print('   Decision made: GCP')

# 7. Contact
print()
print('7. Contact management...')
contact = ea.add_contact('Alice Chen', email='alice@company.com',
                        role='Tech Lead', organization='Engineering',
                        relationship='colleague', department='Engineering',
                        preferred_contact='slack', timezone='PST')
print(f'   Contact: {contact}')

# 8. Inbox capture
print()
print('8. Inbox capture...')
item = ea.capture_inbox('Follow up with vendor on contract renewal',
                       title='Vendor followup', priority=2, tags=['admin'])
print(f'   Captured: {item}')

# 9. Quick capture
print()
print('9. Quick capture...')
qc = ea.capture_quick('Idea: automate weekly report generation',
                     content_type='text', source='widget', tags=['automation', 'idea'])
print(f'   Quick capture: {qc}')

# 9.5 Habits
print()
print('9.5 Habits...')
h1 = ea.add_habit('Daily exercise', frequency='daily', duration_minutes=30,
                  preferred_time='morning', category='health', trigger='wake up')
h2 = ea.add_habit('Read 20 pages', frequency='daily', duration_minutes=30,
                  preferred_time='evening', category='learning', trigger='after dinner')
h3 = ea.add_habit('Weekly review', frequency='weekly', duration_minutes=60,
                  preferred_time='friday_afternoon', category='productivity')
print(f'   Habits: {h1}, {h2}, {h3}')

# Complete habits
ea.complete_habit(h1, quality_score=8)
ea.complete_habit(h2, quality_score=7)
print('   Completed exercise and reading')

# 10. Focus session
print()
print('10. Focus session...')
fs = ea.start_focus_session(t1, duration=50, session_type='deep_work')
time.sleep(1)  # Simulate work
ea.end_focus_session(fs, actual_duration=52, interruptions=1, productivity_score=8)
print('   Focus session completed')

# 11. Energy log
print()
print('11. Energy tracking...')
ea.log_energy(8, focus=7, mood='good', activity='working on report')
ea.log_energy(6, focus=5, mood='tired', activity='after lunch')
print('   Energy logged')

# 12. Delegation
print()
print('12. Delegation...')
del_id = ea.delegate_task(t2, 'Alice Chen', 
                         expected_completion=now + 86400,
                         instructions='Prepare slides for team standup',
                         follow_up_date=now + 43200)
print(f'   Delegated: {del_id}')

# 13. Dashboard
print()
print('13. Dashboard...')
dash = ea.get_dashboard()
for k, v in dash.items():
    print(f'   {k}: {v}')

# 14. Prioritized tasks
print()
print('14. Prioritized tasks...')
priorities = ea.get_prioritized_tasks(5)
for i, t in enumerate(priorities, 1):
    print(f'   {i}. {t["title"]} (score: {t["priority_score"]:.1f})')

# 15. Schedule suggestion
print()
print('15. Schedule suggestion...')
sched = ea.suggest_schedule()
print(f'   Available: {sched["available_hours"]}h')
print(f'   Scheduled: {len(sched["scheduled_tasks"])} tasks')
print(f'   Buffer: {sched["buffer_minutes"]}min')

# 16. Morning briefing
print()
print('16. Morning briefing:')
brief = ea.morning_briefing()
print(brief)

# 17. Final debug
print()
print('17. Final debug:')
print(ea.ea_debug())

print()
print('=== ALL TESTS PASSED ===')