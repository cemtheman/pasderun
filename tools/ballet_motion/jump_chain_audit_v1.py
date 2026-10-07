"""Independent phase/boundary audit of measured jump records.

Root continuity uses the existing plie 1e-4 armature-unit tolerance.
This is a kinematic review-grid audit, never a force/dynamics claim.
"""
import math
BOUNDARIES=(.2,.32,.35,.55,.63,.73)
ROOT_CONTINUITY_LIMIT=1e-4

def audit_jump_report(report):
    records=sorted((s for key,s in report['samples'].items() if key.startswith('candidate/')),key=lambda s:s['time_normalized'])
    errors=[]
    def sample(t):
        matches=[s for s in records if abs(s['time_normalized']-t)<1e-10]
        if len(matches)!=1:raise ValueError(f'Missing/ambiguous required sample {t}')
        return matches[0]
    if report['machine_status']!='PASS':errors.append('renderer_machine_fail')
    if {s['intent']['state'] for s in records}!={'PREPARATION','TAKEOFF','FLIGHT','LANDING'}:errors.append('phase_coverage')
    maximum_boundary_root_step=0.
    for t in BOUNDARIES:
        sample(t)
        a,b=sample(t-1e-6),sample(t+1e-6)
        step=math.dist(a['root_translation'],b['root_translation'])
        maximum_boundary_root_step=max(maximum_boundary_root_step,step)
        if step>ROOT_CONTINUITY_LIMIT:errors.append(f'root_discontinuity:{t}')
    if sample(.35)['intent']['state']!='TAKEOFF':errors.append('release_contact_semantics')
    push=sample(.32)['intent']
    if push['knee_flexion_deg']>1e-6 or push['foot_rise_progress']>=1:errors.append('extension_push_sequence')
    first=sample(.55)['intent']
    if first['state']!='LANDING' or first['knee_flexion_deg']<8:errors.append('straight_knee_impact')
    if sample(.73)['intent']['knee_flexion_deg']<32-1e-6 or sample(1)['intent']['knee_flexion_deg']>1e-6:errors.append('landing_absorption_return')
    for s in records:
        if s['intent']['state']=='FLIGHT':
            if s['minimum_foot_clearance']<=0:errors.append(f'flight_penetration:{s["time_normalized"]}')
            if set(s['support_roles'].values())!={'NONE'}:errors.append('phantom_flight_support')
    return {'status':'FAIL' if errors else 'PASS','errors':errors,'sample_count':len(records),'maximum_boundary_root_step':maximum_boundary_root_step,'root_continuity_limit':ROOT_CONTINUITY_LIMIT,'scope':'measured four-state kinematic continuity, release/push/flight/landing coverage'}
