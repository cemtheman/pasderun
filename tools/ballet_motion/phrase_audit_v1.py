"""Independent whole-composition continuity audit; input PASS is insufficient."""
import math
from phrase_v1 import BOUNDARIES
from weight_transfer_v1 import rotation_step_degrees

def audit_phrase(report):
    errors=[];metrics={}
    if report['machine_status']!='PASS':errors.append('renderer_machine_fail')
    styles=sorted({k.split('/')[0] for k in report['samples']})
    for style in styles:
        samples=[v for k,v in report['samples'].items() if k.startswith(style+'/')]
        samples.sort(key=lambda r:r['time'])
        def at(t):
            rows=[r for r in samples if abs(r['time']-t)<1e-10]
            if len(rows)!=1:raise ValueError('Missing/ambiguous required sample '+str(t))
            return rows[0]
        step=0.
        for t in BOUNDARIES:
            at(t);a,b=at(t-1e-6),at(t+1e-6)
            d=math.dist(a['root_translation'],b['root_translation']);step=max(step,d)
            if d>1e-4:errors.append(style+':boundary_root')
            for n,q in a['orientations_wxyz'].items():
                if rotation_step_degrees(q,b['orientations_wxyz'][n])>30:errors.append(style+':boundary_rotation')
        a,b=at(0),at(1)
        closure=math.dist(a['root_translation'],b['root_translation'])
        if closure>1e-4:errors.append(style+':closure_root')
        if any(rotation_step_degrees(q,b['orientations_wxyz'][n])>1e-3 for n,q in a['orientations_wxyz'].items()):errors.append(style+':closure_pose')
        if {r['intent']['primitive'] for r in samples}!={'PLIE','TRANSFER','SUPPORTED_SETTLE','RETURN','CLOSURE'}:errors.append(style+':primitive_coverage')
        settled=[r for r in samples if r['intent']['primitive']=='SUPPORTED_SETTLE']
        if not settled or any(r['intent']['roles']!={'left':'SUPPORT','right':'TOUCH'} for r in settled):errors.append(style+':support_asymmetry')
        if any(r['intent']['contact_policy']!='FULL_FOOT' for r in samples):errors.append(style+':unexpected_contact')
        metrics[style]={'sample_count':len(samples),'max_boundary_root_step':step,'closure_root_error':closure,
                        'min_support_margin':min(r['balance']['signed_balance_margin'] for r in samples),
                        'max_plant_drift':max(r['plant_drift'] for r in samples),
                        'max_joint_step_deg':max(r['joint_step_deg'] for r in samples)}
    if set(styles)!={'clear','soft'}:errors.append('style_reuse_coverage')
    return {'status':'FAIL' if errors else 'PASS','errors':errors,'metrics':metrics,'scope':'new complete phrase; exact boundaries and closure, not isolated pose approval'}
