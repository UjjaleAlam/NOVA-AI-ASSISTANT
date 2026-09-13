import core.digital_twin as dt
import time
from datetime import datetime, timedelta

print('=== DIGITAL TWIN AGENT TEST ===')

# 1. Debug
print('1. Debug:')
print(dt.dt_debug())

# 2. Capture snapshot
print('\n2. Capturing snapshot...')
snap_id = dt.capture_snapshot()
print(f'   Snapshot: {snap_id}')

# 3. Log activities
print('\n3. Logging activities...')
now = time.time()
a1 = dt.log_activity('app_switch', 'vscode', 'chrome', {'from': 'vscode', 'to': 'chrome'})
a2 = dt.log_activity('file_open', 'vscode', '', {'file': '/home/user/project/main.py'})
a3 = dt.log_activity('web_visit', 'chrome', '', {'url': 'https://github.com'})
a4 = dt.log_activity('command', 'terminal', '', {'command': 'git status'})
print(f'   Activities: {a1}, {a2}, {a3}, {a4}')

# 4. Get activities
print('\n4. Querying activities...')
activities = dt.get_activities(limit=10)
for a in activities:
    print(f'   {datetime.fromtimestamp(a["timestamp"]).strftime("%H:%M:%S")} {a["activity_type"]}: {a["source_app"]} -> {a["target_app"]}')

# 5. Sessions
print('\n5. Sessions...')
sess_id = dt.start_session('deep_work', ['Finish report', 'Code review'], 'proj_123')
print(f'   Started session: {sess_id}')
dt.end_session(sess_id, ['Finished report', 'Reviewed PR'], focus_score=8, interruptions=2)
print('   Session ended')

# 6. Project states
print('\n6. Project states...')
proj_id = dt.create_project_state('Digital Twin Agent', 'Build digital twin agent',
                                   category='development', priority=1,
                                   target_date=time.time() + 86400*14)
print(f'   Created project: {proj_id}')
dt.projects.update_progress(proj_id, 25.0)
print('   Progress updated to 25%')

# 6. Project states listing
print('\n6b. Listing projects...')
projects = dt.list_project_states()
for p in projects:
    print(f'   {p["id"]}: {p["name"]} ({p["progress"]}%)')

# 7. Context markers
print('\n7. Context markers...')
m1 = dt.create_context_marker('milestone', 'Finished core architecture',
                              context_type='milestone', importance=9,
                              tags=['architecture', 'milestone'])
m2 = dt.create_context_marker('idea', 'Add real-time sync',
                              context_type='idea', importance=6,
                              tags=['feature', 'sync'])
print(f'   Markers: {m1}, {m2}')

# 8. Patterns
print('\n8. Pattern recognition...')
workflows = dt.get_workflow_patterns(7)
for w in workflows[:3]:
    print(f'   {w["transition"]}: {w["count"]} times')

productive = dt.get_productive_hours(30)
print(f'   Productive hours: {productive}')

# 8b. App usage analysis
app_usage = dt.patterns.analyze_app_usage(7)
print(f'   App usage (top 5): {sorted(app_usage.get("app_usage", {}).items(), key=lambda x: x[1], reverse=True)[:5]}')

# 9. Context markers
print('\n9. Context markers...')
markers = dt.get_context_markers()
for m in markers[:3]:
    print(f'   {m["label"]} ({m["context_type"]}): {m["description"][:50]}...')

# 10. Sync
print('\n10. Sync...')
sync_id = dt.queue_sync('task', 'task_123', 'update', {'status': 'completed'})
print(f'   Queued sync: {sync_id}')
pending = dt.get_pending_syncs()
print(f'   Pending syncs: {len(pending)}')

# 11. Dashboard
print('\n11. Dashboard...')
dash = dt.get_dashboard()
for k, v in dash.items():
    print(f'   {k}: {v}')

# 12. Timeline
print('\n12. Timeline (24h)...')
timeline = dt.get_timeline(24)
for t in timeline[:5]:
    print(f'   {datetime.fromtimestamp(t["timestamp"]).strftime("%H:%M:%S")} {t["activity_type"]}: {t.get("source_app", "")} -> {t.get("target_app", "")}')

# 13. Productivity report
print('\n13. Productivity report...')
report = dt.get_productivity_report(7)
for k, v in report.items():
    print(f'   {k}: {v}')

# 14. Reconstruct workspace
print('\n14. Reconstruct workspace...')
ws = dt.reconstruct_workspace()
print(f'   Apps: {len(ws.get("applications", []))}')
print(f'   Active window: {ws.get("active_window", {}).get("title", "N/A")}')

# 14b. Snapshot details
print('\n14b. Snapshot details...')
snaps = dt.snapshots.get_snapshots(limit=1)
if snaps:
    snap = snaps[0]
    print(f'   Snapshot: {snap["id"]}')
    print(f'   Apps: {len(snap["applications"])}')
    print(f'   Active window: {snap["active_window"]}')

# 15. Snapshots with activity
print('\n15. Activity from snapshots...')
snaps = dt.snapshots.get_snapshots(limit=5)
for s in snaps:
    print(f'   {datetime.fromtimestamp(s["timestamp"]).strftime("%H:%M:%S")} - {s["user_activity"]} - {len(s["applications"])} apps')

print('\n=== ALL TESTS PASSED ===')