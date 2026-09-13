# Test imports that commands.py uses
from core.audit_agent import (
    audit_debug, list_engagements, create_audit_engagement,
    start_audit, complete_audit, create_audit_program,
    create_workpaper, update_workpaper, create_finding,
    add_evidence, assess_risk, create_audit_sample,
    register_framework, assess_compliance, generate_audit_report,
    create_quality_review, log_audit_time, create_engagement_budget,
    get_engagement_budget
)
print('All imports successful!')

# Test list_engagements format
audits = list_engagements()
if audits:
    a = audits[0]
    print(f"  • {a['engagement_number']} - {a['client_name']} ({a['status']})")

# Test create_audit_engagement return type
import time
eng = create_audit_engagement(
    'Test Client 3', 'client_004', 'financial', 'Full audit',
    time.time(), time.time() + 86400*60,
    'Lead Auditor', ['Alice', 'Bob'], 25000, 'Planning notes'
)
print(f"Created: {eng.engagement_number} ({eng.id})")