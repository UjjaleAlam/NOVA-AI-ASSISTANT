import core.timeline_memory as tm
import time
from datetime import datetime, timedelta

print('=== TIMELINE MEMORY AGENT TEST ===')

# 1. Debug
print('1. Debug:')
print(tm.tm_debug())

# 2. Add timeline events
print()
print('2. Adding events...')
now = time.time()
e1 = tm.add_timeline_event('code', 'Built login feature', now - 7200, 'Implemented JWT auth', 'work', 3600, 'auto', ['python', 'auth'], {'lines': 200})
e2 = tm.add_timeline_event('meeting', 'Team standup', now - 3600, 'Daily sync', 'work', 1800, 'manual', ['meeting', 'team'])
e3 = tm.add_timeline_event('learning', 'Read ML paper', now - 1800, 'Attention mechanisms', 'learning', 2700, 'manual', ['ml', 'paper'])
e4 = tm.add_timeline_event('break', 'Coffee break', now - 600, '', 'personal', 600, 'auto', ['break'])
e5 = tm.add_timeline_event('code', 'Fixed bug #42', now, 'Off-by-one error', 'work', 900, 'auto', ['bugfix'])
print('   Events added:', e1, e2, e3, e4, e5)

# 3. Query events
print()
print('3. Querying events...')
events = tm.get_timeline_events(limit=10)
for e in events:
    print('   ' + datetime.fromtimestamp(e['timestamp']).strftime('%H:%M') + ' ' + e['event_type'] + ': ' + e['title'])

# 4. Day timeline
print()
print('4. Today timeline:')
today = datetime.now().strftime('%Y-%m-%d')
day_events = tm.get_day_timeline(today)
for e in day_events:
    print('   ' + datetime.fromtimestamp(e['timestamp']).strftime('%H:%M') + ' ' + e['title'])

# 5. Search
print()
print('5. Search:')
results = tm.search_timeline('bug')
for r in results:
    print('   ' + r['title'])

# 6. Daily summary
print()
print('6. Daily summary:')
summary = tm.get_daily_summary(today)
print('   Events:', summary['total_events'])
print('   Duration:', round(summary['total_duration_seconds']/3600, 1), 'h')
print('   Productivity:', summary['productivity_score'])
print('   Focus:', round(summary['focus_time_seconds']/3600, 1), 'h')
print('   Types:', summary['event_types'])

# 7. Week summary
print()
print('7. Week summary:')
week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime('%Y-%m-%d')
week = tm.get_week_summary(week_start)
print('   Total events:', week['total_events'])
print('   Avg productivity:', round(week['avg_productivity'], 1))

# 8. Habits
print()
print('8. Habits:')
h1 = tm.create_habit('Exercise', 'daily', duration_minutes=30, category='health')
h2 = tm.create_habit('Read', 'daily', duration_minutes=20, category='learning')
h3 = tm.create_habit('Code', 'daily', duration_minutes=60, category='work')
print('   Created:', h1, h2, h3)

tm.complete_habit(h1, quality=8)
tm.complete_habit(h2, quality=7)
print('   Completed exercise, reading')

today_habits = tm.get_today_habits()
for h in today_habits:
    status = 'DONE' if h['completed_today'] else 'PENDING'
    print('   ' + h['name'] + ': ' + status + ' (streak: ' + str(h['streak']) + ')')

# 9. Goals
print()
print('9. Goals:')
g1 = tm.create_goal('Launch MVP', goal_type='outcome', category='career', target_date=time.time()+86400*30, target_value=1, target_unit='launch')
g2 = tm.create_goal('Learn Rust', goal_type='learning', category='learning', target_date=time.time()+86400*90, target_value=100, target_unit='hours')
print('   Created:', g1, g2)

tm.update_goal_progress(g1, 0.3)
print('   MVP progress: 30%')

goals = tm.get_goals('active')
for g in goals:
    print('   ' + g['title'] + ': ' + str(g['progress']) + '%')

# 10. Memory anchors
print()
print('10. Memory anchors:')
a1 = tm.create_memory_anchor('achievement', 'First production deploy', significance=9, emotions=['pride', 'relief'], people=['team'])
a2 = tm.create_memory_anchor('insight', 'Realized caching strategy', significance=7, emotions=['excitement'])
print('   Anchors:', a1, a2)

# 11. Narrative threads
print()
print('11. Narrative threads:')
nt = tm.create_narrative_thread('Auth System', 'project', themes=['auth', 'security'], people=['alice', 'bob'])
tm.add_event_to_thread(nt, e1)
tm.add_event_to_thread(nt, e5)
thread = tm.get_narrative_thread(nt)
print('   Thread:', thread['name'], 'events:', len(thread['events']))

# 12. Temporal queries
print()
print('12. Temporal queries:')
heatmap = tm.get_activity_heatmap(7)
print('   Heatmap days:', len(heatmap))

allocation = tm.get_time_allocation(7)
print('   Time allocation:', allocation)

patterns = tm.find_temporal_patterns(2)
for p in patterns[:3]:
    print('   Pattern:', p['description'])

correlations = tm.correlate_event_types('code', 'meeting', 4)
print('   Code-Meeting correlations:', len(correlations))

# 13. Final debug
print()
print('13. Final debug:')
print(tm.tm_debug())

print()
print('=== ALL TESTS PASSED ===')