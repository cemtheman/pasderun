import unittest
from jump_chain_v1 import jump_intent
class JumpTests(unittest.TestCase):
    def test_states_and_no_straight_knee_impact(self):
        self.assertEqual([jump_intent(t)['state'] for t in (0,.25,.45,.55)],['PREPARATION','TAKEOFF','FLIGHT','LANDING'])
        self.assertEqual(jump_intent(.55)['knee_flexion_deg'],8)
        self.assertEqual(jump_intent(1)['knee_flexion_deg'],0)
    def test_bounded_chain_and_parabola(self):
        samples=[jump_intent(i/1000) for i in range(1001)]
        self.assertTrue(all(0<=s['knee_flexion_deg']<=32 and 0<=s['foot_rise_progress']<=1 and 0<=s['toe_flexion_deg']<=35 for s in samples))
        self.assertAlmostEqual(jump_intent(.45)['flight_clearance'],.18)
        self.assertAlmostEqual(8*.18/.4**2,9.)
    def test_knee_extension_precedes_completed_ankle_push(self):
        s=jump_intent(.32);self.assertAlmostEqual(s['knee_flexion_deg'],0);self.assertLess(s['foot_rise_progress'],1)
        for t in (-.1,1.1,float('nan')):
            with self.assertRaises(ValueError):jump_intent(t)
