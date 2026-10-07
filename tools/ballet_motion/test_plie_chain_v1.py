import unittest
from plie_chain_v1 import plie_progress,chain_intent
class PlieTests(unittest.TestCase):
    def test_endpoints_reversal_and_bounds(self):
        for lag in (-.1,0,.1):
            values=[plie_progress(i/100,lag) for i in range(101)]
            self.assertEqual(values[0],0);self.assertEqual(values[50],1);self.assertEqual(values[-1],0)
            self.assertTrue(all(a<=b for a,b in zip(values[:50],values[1:51])))
            self.assertTrue(all(a>=b for a,b in zip(values[50:],values[51:])))
            self.assertTrue(all(0<=v<=1 for v in values))
    def test_phase_offsets_do_not_change_anchors_or_turnout(self):
        mid=chain_intent(.25);self.assertGreater(mid['hip_reference_flexion_deg']/18,mid['knee_flexion_deg']/32)
        for t in (0,.5,1):self.assertEqual(chain_intent(t)['independent_foot_yaw_deg'],0)
    def test_invalid_inputs_fail(self):
        for t,l in [(float('nan'),0),(1.1,0),(.5,.2)]:
            with self.assertRaises(ValueError):plie_progress(t,l)
