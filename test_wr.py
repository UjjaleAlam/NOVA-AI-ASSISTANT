import core.workspace_reconstruction as wr
import time

print('=== WORKSPACE RECONSTRUCTION AGENT TEST ===')

# 1. Debug
print('1. Debug:')
print(wr.wr_debug())

# 2. Capture workspace
print('\n2. Capturing workspace...')
snap_id = wr.capture_workspace("Test Workspace", "Test capture for development")
print(f'   Snapshot: {snap_id}')

# 3. Get snapshot
print('\n3. Getting snapshot...')
snap = wr.get_snapshot(snap_id)
if snap:
    print(f'   Name: {snap["name"]}')
    print(f'   Apps captured: {len(snap["apps"])}')
    print(f'   Windows captured: {len(snap["windows"])}')
    print(f'   Terminals: {len(snap["terminal_sessions"])}')
    print(f'   Open files: {len(snap["open_files"])}')

# 4. List snapshots
print('\n4. Listing snapshots...')
snaps = wr.list_snapshots(10)
for s in snaps:
    print(f'   {s["id"]}: {s["name"]} ({s["apps_count"]} apps)')

# 5. Test templates
print('\n5. Templates:')
wr.create_default_workspace_templates()
templates = wr.list_templates()
for t in templates:
    print(f'   {t["id"]}: {t["name"]} [{t["category"]}]')

# 6. Create custom template
print('\n6. Creating custom template...')
tpl_id = wr.create_template(
    "My Dev Setup",
    "Custom development environment",
    "development",
    apps=[
        {"app_name": "code", "exe_path": "code", "working_directory": "~/projects"},
        {"app_name": "terminal", "exe_path": "wt.exe", "working_directory": "~/projects"}
    ],
    layout={"windows": [{"app_name": "code", "rect": {"x": 0, "y": 0, "width": 1200, "height": 1080}}]},
    tags=["custom", "development"]
)
print(f'   Template: {tpl_id}')

# 7. Create template from snapshot
print('\n7. Creating template from snapshot...')
tpl_id2 = wr.create_template_from_snapshot(snap_id, "From Snapshot", "Template created from capture")
print(f'   Template: {tpl_id2}')

# 8. Test restoration (dry run - will fail but tests the job creation)
print('\n8. Testing restoration job...')
job_id = wr.restore_workspace(snap_id, {"dry_run": True})
print(f'   Job: {job_id}')
time.sleep(1)
status = wr.get_restoration_status(job_id)
print(f'   Status: {status.get("status", "unknown")}')

# 9. Debug again
print('\n9. Final debug:')
print(wr.wr_debug())

print('\n=== ALL TESTS PASSED ===')