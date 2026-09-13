from core.audit_agent import audit_agent
import time

print('Testing audit agent...')
eng = audit_agent.create_engagement('Test Client', 'client_001', 'financial', 'Full audit', time.time(), time.time() + 86400*90, 'John Smith', ['Jane Doe'], 50000, 'Test audit')
print('Created engagement: {} ({})'.format(eng['engagement_number'], eng['id']))

# Test creating a workpaper
wp_id = audit_agent.create_workpaper(eng['id'], 'A-1', 'Cash Count', 'Cash count workpaper')
print('Created workpaper:', wp_id)

# Test creating a finding
fid = audit_agent.create_finding(eng['id'], 'Cash discrepancy', 'Cash count off by 50 dollars', 'medium', 'error', 'WP-001', 'Miscount', 'Financial misstatement', 'Recount cash', 'John Smith', time.time() + 86400*7)
print('Created finding:', fid)

# Test adding evidence
ev_id = audit_agent.add_evidence(eng['id'], 'document', 'Bank statement', 'Bank of America', 'bank_stmt.pdf', 'John Smith')
print('Added evidence:', ev_id)

# Test risk assessment
risk_id = audit_agent.assess_risk(eng['id'], 'revenue', 'Revenue recognition risk', 'likely', 'high')
print('Risk assessed:', risk_id)

# Test creating a sample
sample = audit_agent.create_audit_sample(eng['id'], 'revenue', 10000, 0.95, 0.05, 0.01)
print('Created sample:', sample)

# Test creating a finding
fid = audit_agent.create_finding(eng['id'], 'Test Finding', 'Test description', 'high', 'error')
print('Created finding:', fid)

# Test audit debug
from core.audit_agent import audit_debug
print()
print('Audit Debug:')
print(audit_debug())