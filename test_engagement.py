import core.audit_agent as aa
mgr = aa.AuditEngagementManager()
eng = mgr.create_engagement(
    client_name='Test Corp',
    client_id='test_001',
    audit_type='financial',
    scope='Test audit',
    planned_start=1700000000,
    planned_end=1800000000,
    lead_auditor='Test Auditor',
    team_members=['Alice', 'Bob'],
    materiality=10000.0,
    planning_notes='Test notes'
)
print('Created:', eng)
if eng:
    retrieved = mgr.get_engagement(eng['id'])
    print('Retrieved:', retrieved)