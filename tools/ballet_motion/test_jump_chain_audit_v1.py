import copy
import unittest
from jump_chain_v1 import jump_intent,jump_review_times
from jump_chain_audit_v1 import audit_jump_report


def fixture():
    samples={}
    for i,t in enumerate(jump_review_times(True)):
        intent=jump_intent(t);air=intent['state']=='FLIGHT'
        samples[f'candidate/{i:02d}']={'time_normalized':t,'intent':intent,'root_translation':[0,0,t*.05],'minimum_foot_clearance':.01 if air else 0,'support_roles':{'left':'NONE' if air else 'SUPPORT','right':'NONE' if air else 'SUPPORT'}}
    return {'machine_status':'PASS','samples':samples}

class JumpAuditTests(unittest.TestCase):
    def test_complete_grid_is_required(self):
        r=fixture();self.assertEqual(audit_jump_report(r)['status'],'PASS')
        key=next(k for k,v in r['samples'].items() if v['time_normalized']==.55)
        del r['samples'][key]
        with self.assertRaisesRegex(ValueError,'required sample'):audit_jump_report(r)

    def test_measured_contact_boundary_jump_is_rejected(self):
        r=fixture();v=next(v for v in r['samples'].values() if abs(v['time_normalized']-.630001)<1e-10)
        v['root_translation'][2]+=.00033
        self.assertIn('root_discontinuity:0.63',audit_jump_report(r)['errors'])

    def test_airborne_penetration_and_false_support_are_rejected(self):
        r=fixture();v=next(v for v in r['samples'].values() if v['intent']['state']=='FLIGHT')
        v['minimum_foot_clearance']=-.0003;v['support_roles']['left']='SUPPORT'
        result=audit_jump_report(r);self.assertEqual(result['status'],'FAIL');self.assertIn('phantom_flight_support',result['errors'])

    def test_first_contact_must_absorb_with_flexed_knees(self):
        r=fixture();v=next(v for v in r['samples'].values() if v['time_normalized']==.55)
        v['intent']['knee_flexion_deg']=0
        self.assertIn('straight_knee_impact',audit_jump_report(r)['errors'])
