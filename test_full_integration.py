import core.audit_agent as aa
import time

# Full integration test
print('=== AUDIT AGENT FULL INTEGRATION TEST ===')

# 1. Create engagement
eng = aa.create_audit_engagement(
    'Integration Test Corp', 'int_001', 'financial', 'Full financial audit',
    time.time(), time.time() + 86400*90,
    'Lead Auditor', ['Senior 1', 'Senior 2', 'Staff 1'], 
    75000.0, 'Integration test engagement'
)
eid = eng.id
print(f'1. Engagement created: {eng.engagement_number} ({eid})')

# 2. Create audit programs
prog1 = aa.create_audit_program(eid, 'Revenue', 'Test revenue recognition',
    ['Test sales cutoff', 'Test returns', 'Analytical procedures'], 'high', 'Senior 1')
prog2 = aa.create_audit_program(eid, 'Cash', 'Test cash balances',
    ['Bank confirmations', 'Bank reconciliations', 'Cutoff testing'], 'high', 'Senior 2')
print(f'2. Programs created: {prog1}, {prog2}')

# 3. Create workpapers
wp1 = aa.create_workpaper(eid, 'A-1', 'Revenue Cutoff Testing', 'Test revenue around year-end', prog1, 'Staff 1')
wp2 = aa.create_workpaper(eid, 'B-1', 'Bank Reconciliations', 'Test all bank recs', prog2, 'Staff 1')
print(f'3. Workpapers created: {wp1}, {wp2}')

# 4. Create findings
f1 = aa.create_finding(eid, 'Revenue cutoff error', 'Revenue recognized in wrong period',
    'high', 'financial', wp1, 'F-001')
f2 = aa.create_finding(eid, 'Unreconciled bank items', 'Stale dated checks not cleared',
    'medium', 'financial', wp2, 'F-002')
print(f'4. Findings created: {f1}, {f2}')

# 5. Add evidence
e1 = aa.add_evidence(eid, 'document', 'Sales invoices near year-end', 'Client', '/evidence/invoices.pdf', 'Staff 1', wp1, f1, 'direct', 'high')
e2 = aa.add_evidence(eid, 'confirmation', 'Bank confirmation', 'Bank of America', '', 'Staff 1', wp2, f2, 'direct', 'high')
print(f'5. Evidence added: {e1}, {e2}')

# 6. Risk assessment
r1 = aa.assess_risk(eid, 'Revenue', 'Premature revenue recognition', 'high', 'high')
r2 = aa.assess_risk(eid, 'Cash', 'Misappropriation of cash', 'medium', 'high')
print(f'6. Risks assessed: {r1}, {r2}')

# 7. Sampling
s1 = aa.create_audit_sample(eid, 'Revenue', 5000, 0.95, 0.05, 0.01)
s2 = aa.create_audit_sample(eid, 'Cash', 200, 0.95, 0.05, 0.01)
print(f'7. Samples created: {s1}, {s2}')

# 8. Compliance frameworks
fw_sox = aa.load_framework_template('SOX')
fw_iso = aa.load_framework_template('ISO27001')
print(f'8. Frameworks loaded: SOX={fw_sox}, ISO27001={fw_iso}')

# 9. Compliance assessment
comp1 = aa.assess_compliance(eid, fw_sox)
comp2 = aa.assess_compliance(eid, fw_iso)
print(f'9. Compliance assessed')

# 10. Advanced features
letter = aa.EngagementLetterGenerator.generate(eid)
rep = aa.ManagementRepLetter.generate(eid)
gc = aa.GoingConcernAssessment.assess(eid, {'negative_cash_flow': False})
fraud = aa.FraudRiskAssessment.assess(eid)
itgc = aa.ITGCManager.create_itgc_program(eid)
jet = aa.JournalEntryTesting.create_jet_program(eid)
plan_checklist = aa.AuditChecklist.planning_checklist(eid)
comp_checklist = aa.AuditChecklist.completion_checklist(eid)
qc_checklist = aa.QualityControlChecklist.isqc1_checklist()
print('10. Advanced features: ITGC=%d, JET=%d, Plan=%d areas, Comp=%d areas, QC=%d elements' % (len(itgc), len(jet), len(plan_checklist), len(comp_checklist), len(qc_checklist)))

# 11. Sample size calculators
attr = aa.SampleSizeCalculator.attribute_sampling(1000, 0.95, 0.05, 0.01)
var = aa.SampleSizeCalculator.variable_sampling(1000, 0.95, 50000, 10000, 20000)
mus = aa.SampleSizeCalculator.mus_sampling(1000000, 0.95, 50000, 10000, 1000)
print('11. Sampling: Attribute=%d, Variable=%d, MUS=%d' % (attr['sample_size'], var['sample_size'], mus['sample_size']))

# 12. Reports
rpt = aa.generate_audit_report(eid, 'management_letter')
qr = aa.create_quality_review(eid, wp1, 'EQCR Reviewer', 'engagement')
print('12. Reports: %s, QR=%s' % (rpt, qr))

# 13. Time tracking
t1 = aa.log_audit_time(eid, 'senior1', 20.5, 'planning', 'Risk assessment and planning', True, 200)
t2 = aa.log_audit_time(eid, 'senior2', 15.0, 'fieldwork', 'Revenue testing', True, 200)
t3 = aa.log_audit_time(eid, 'staff1', 30.0, 'fieldwork', 'Cash testing', True, 150)
print('13. Time logged: %s, %s, %s' % (t1, t2, t3))

# 14. Budget
budget = aa.create_engagement_budget(eid, 200, 35000)
budget_info = aa.get_engagement_budget(budget)
print('14. Budget: %s' % budget_info)

# 15. Debug summary
print()
print('=== FINAL DATABASE STATE ===')
print(aa.audit_debug())

print()
print('=== ALL TESTS PASSED ===')