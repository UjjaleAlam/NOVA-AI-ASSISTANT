import core.continuous_awareness as ca
import time

# Start awareness and capture some snapshots
ca.start_awareness()
time.sleep(2)
ca.record_app_launch('test_app')
ca.record_file_open('/test/file.txt')
time.sleep(2)
status = ca.get_awareness_status()
print('Status:', status)

# Get snapshots for session
session_id = status['monitor']['session_id']
snapshots = ca.get_snapshots_for_session(session_id, 10)
print('Snapshots:', len(snapshots))
for s in snapshots:
    print('  ' + s['id'] + ': presence=' + s['user_presence'] + ', file=' + str(s['snapshot_file']) + ', size=' + str(s['file_size_bytes']))

# Load full snapshot data
if snapshots:
    data = ca.get_snapshot_data(snapshots[0]['id'])
    print('Full snapshot data keys:', list(data.keys()) if data else 'None')

# Stop awareness
session = ca.stop_awareness()
print('Session ended:', session['id'])

# Check debug info
print()
print(ca.ca_debug())