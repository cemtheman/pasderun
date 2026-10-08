import unittest
from phrase_v1 import phrase_intent,review_times
from phrase_audit_v1 import audit_phrase

def fixture():
    samples={}
    for style in ('clear','soft'):
        for i,t in enumerate(review_times()):
            samples[f'{style}/{i:03d}']={'time':t,'intent':phrase_intent(t,style),'root_translation':[0,0,0],
                'orientations_wxyz':{'Hand':[1,0,0,0]},'balance':{'signed_balance_margin':.01},'plant_drift':0,'joint_step_deg':0}
    return {'machine_status':'PASS','samples':samples}

class PhraseAuditTests(unittest.TestCase):
    def test_complete_phrase_is_required(self):
        r=fixture();self.assertEqual(audit_phrase(r)['status'],'PASS')
        k=next(k for k,v in r['samples'].items() if k.startswith('soft/') and v['time']==.8)
        del r['samples'][k]
        with self.assertRaises(ValueError):audit_phrase(r)

    def test_key_pose_pass_does_not_hide_boundary_snap(self):
        r=fixture();v=next(v for v in r['samples'].values() if abs(v['time']-.800001)<1e-10);v['root_translation'][0]=.0003
        self.assertEqual(audit_phrase(r)['status'],'FAIL')

    def test_closure_and_style_coverage_are_not_optional(self):
        r=fixture();v=next(v for k,v in r['samples'].items() if k.startswith('clear/') and v['time']==1);v['root_translation'][0]=.001
        self.assertIn('clear:closure_root',audit_phrase(r)['errors'])
        r=fixture();r['samples']={k:v for k,v in r['samples'].items() if k.startswith('clear/')}
        self.assertIn('style_reuse_coverage',audit_phrase(r)['errors'])
