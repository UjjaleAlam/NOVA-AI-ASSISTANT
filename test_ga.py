import core.goal_awareness as ga
import time
from datetime import datetime, timedelta

print('=== GOAL AWARENESS AGENT TEST ===')

# 1. Debug
print('1. Debug:')
print(ga.ga_debug())

# 2. Create goals
print()
print('2. Creating goals...')
now = time.time()

# Parent goal
g1 = ga.create_goal('Launch SaaS MVP', 'project', 'career', 'quarterly',
                    target_date=now + 86400*90, target_value=1, target_unit='launch',
                    priority=1, description='Full product launch')
print('   Parent goal:', g1)

# Sub-goals
g2 = ga.create_goal('Build authentication', 'outcome', 'career', 'monthly',
                    target_date=now + 86400*30, target_value=100, target_unit='%',
                    priority=1, parent_goal_id=g1)
print('   Sub-goal 1:', g2)

g3 = ga.create_goal('Design dashboard', 'outcome', 'career', 'monthly',
                    target_date=now + 86400*45, target_value=100, target_unit='%',
                    priority=2, parent_goal_id=g1)
print('   Sub-goal 2:', g3)

g4 = ga.create_goal('Exercise 3x/week', 'habit', 'health', 'weekly',
                    target_date=now + 86400*12, target_value=36, target_unit='sessions',
                    priority=2)
print('   Health goal:', g4)

# 3. Milestones
print()
print('3. Adding milestones...')
ga.add_milestone(g2, 'Setup auth library', 1, target_date=now + 86400*7)
ga.add_milestone(g2, 'Implement JWT', 2, target_date=now + 86400*14)
ga.add_milestone(g2, 'Add OAuth providers', 3, target_date=now + 86400*21)
ga.add_milestone(g2, 'Testing & docs', 4, target_date=now + 86400*28)

ga.add_milestone(g3, 'Wireframes', 1, target_date=now + 86400*10)
ga.add_milestone(g3, 'Frontend components', 2, target_date=now + 86400*25)
ga.add_milestone(g3, 'Backend API', 3, target_date=now + 86400*35)
ga.add_milestone(g3, 'Integration', 4, target_date=now + 86400*42)

# 4. Progress
print()
print('4. Updating progress...')
ga.update_goal_progress(g2, 25, 'Auth library setup complete')
ga.update_goal_progress(g3, 10, 'Wireframes started')
ga.update_goal_progress(g4, 3, 'Week 1 done')

# 5. Time allocation
print()
print('5. Allocating time...')
today = datetime.now().strftime('%Y-%m-%d')
yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
ga.allocate_goal_time(g2, today, 3, 2.5, 4)
ga.allocate_goal_time(g3, today, 2, 1.5, 3)
ga.allocate_goal_time(g2, yesterday, 4, 4, 5)
ga.allocate_goal_time(g4, today, 1, 1, 5)

# 6. Reviews
print()
print('6. Adding review...')
ga.review_goal(g2, 'weekly', rating=8,
              what_worked='Auth library integrated smoothly',
              what_didnt='OAuth config took longer than expected',
              blockers=['OAuth provider rate limits'],
              adjustments=['Add caching layer', 'Pre-register apps'],
              next_actions=['Implement JWT', 'Write tests'])

# 7. Alignment check
print()
print('7. Checking alignment...')
align = ga.check_goal_alignment(g2, g3)
print(f'   Auth vs Dashboard: {align["alignment"]} (strength: {align["strength"]})')

# 8. Dependencies
print()
print('8. Adding dependencies...')
ga.add_goal_dependency(g2, g3, 'blocks')  # Auth blocks dashboard
print('   Auth blocks Dashboard')

# 9. Goal tree
print()
print('9. Goal tree:')
tree = ga.get_goal_tree()
for root in tree['roots']:
    print(f'   {root["title"]} ({root["progress"]}%)')
    for child in root['children']:
        print(f'     - {child["title"]} ({child["progress"]}%)')
        for ms in child['milestones']:
            print(f'       * {ms["title"]}: {ms["status"]}')

# 10. Health check
print()
print('10. Health checks:')
for goal_id in [g1, g2, g3, g4]:
    health = ga.get_goal_health(goal_id)
    g = ga.get_goal(goal_id)
    print(f'   {g["title"]}: {health["health_score"]}/100 - {health["status"]}')
    for rec in health['recommendations']:
        print(f'     -> {rec}')

# 11. Conflicts
print()
print('11. Conflicts:')
conflicts = ga.find_goal_conflicts()
for c in conflicts:
    print(f'   {c["goal_a"]} vs {c["goal_b"]}: {c["strength"]}')

# 12. Weekly priorities
print()
print('12. Weekly priorities:')
priorities = ga.get_weekly_priorities()
for p in priorities:
    print(f'   {p["title"]}: score={p["priority_score"]:.1f}')

# 13. Next actions
print()
print('13. Next actions for g2:')
actions = ga.suggest_goal_actions(g2)
for a in actions:
    print(f'   - {a}')

# 14. Time allocation
print()
print('14. Time allocation:')
alloc = ga.get_goal_time_allocation(g2, 7)
print(f'   Planned: {alloc["planned_hours"]}h, Actual: {alloc["actual_hours"]}h, Efficiency: {alloc["efficiency"]}%')

# 15. Summary
print()
print('15. Active goals summary:')
summary = ga.get_active_goals_summary()
print(f'   Total: {summary["total"]}, Avg progress: {summary["avg_progress"]:.1f}%')
print(f'   By category: {summary["by_category"]}')
print(f'   Overdue: {summary["overdue"]}')

# 16. Debug
print()
print('16. Final debug:')
print(ga.ga_debug())

print()
print('=== ALL TESTS PASSED ===')