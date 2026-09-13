import core.continuous_awareness as ca
import time

print('=== CONTINUOUS AWARENESS AGENT TEST ===')

# 1. Debug
print('1. Debug:')
print(ca.ca_debug())

# 2. Start awareness
print('\n2. Starting awareness...')
session_id = ca.start_awareness()
print(f'   {session_id}')

# 3. Simulate some activity
print('\n3. Recording activity...')
ca.record_app_launch('vscode')
ca.record_app_launch('chrome')
ca.record_app_launch('vscode')
ca.record_window_switch()
ca.record_file_open('/home/user/project/main.py')
ca.record_file_open('/home/user/project/utils.py')
ca.record_app_launch('terminal')

# 4. Check status
print('\n4. Status:')
status = ca.get_awareness_status()
print(f'   {status}')

# 5. Generate suggestions
print('\n5. Proactive suggestions:')
suggestions = ca.get_proactive_suggestions()
for s in suggestions:
    print(f'   [{s["priority"]}] {s["title"]}: {s["description"][:60]}...')

# 6. Generate insights
print('\n6. Insights:')
insights = ca.get_insights()
for i in insights:
    print(f'   [{i["insight_type"]}] {i["title"]}: {i["description"][:60]}...')

# 7. Check anomalies
print('\n7. Anomalies:')
anomalies = ca.get_anomalies()
for a in anomalies:
    print(f'   [{a["severity"]}] {a["type"]}: {a["description"]}')

# 8. Pattern recognition
print('\n8. Pattern recognition:')
patterns = ca.get_patterns()
for p in patterns:
    print(f'   [{p["pattern_type"]}] {p["description"]} (conf: {p["confidence"]})')

# 9. Test session recording
print('\n9. Session recording:')
ca.session_manager.record_suggestion()
ca.session_manager.record_suggestion(accepted=True)
ca.session_manager.record_insight()
ca.session_manager.record_anomaly()

# 10. End session and get summary
print('\n10. Ending session...')
session = ca.stop_awareness()
print(f'   Session: {session["id"]}')
print(f'   Active: {session["total_active_time"]/60:.1f} min')
print(f'   Idle: {session["total_idle_time"]/60:.1f} min')
print(f'   Switches: {session["window_switches"]}')
print(f'   Apps: {session["apps_used"]}')
print(f'   Suggestions: {session["suggestions_generated"]} (accepted: {session["suggestions_accepted"]})')
print(f'   Insights: {session["insights_generated"]}')
print(f'   Anomalies: {session["anomalies_detected"]}')

# 11. Daily summary
print('\n11. Daily summary:')
daily = ca.get_daily_summary()
print(f'   {daily}')

# 12. Recent sessions
print('\n12. Recent sessions:')
sessions = ca.get_recent_sessions()
for s in sessions:
    print(f'   {s["session_id"]}: {s["active_time"]/60:.1f}min active, {len(s["apps"])} apps')

print('\n=== ALL TESTS PASSED ===')