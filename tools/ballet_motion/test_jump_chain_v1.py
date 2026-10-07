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

class JumpBoundaryCoverageTests(unittest.TestCase):
    def test_release_remains_contact_until_positive_flight_time(self):
        self.assertEqual(jump_intent(.35)['state'],'TAKEOFF')
        self.assertEqual(jump_intent(.350001)['state'],'FLIGHT')
        self.assertEqual(jump_intent(.55)['state'],'LANDING')
        self.assertEqual(jump_intent(.55)['knee_flexion_deg'],8)

    def test_boundary_intent_is_continuous(self):
        for t in (.2,.32,.35,.55,.63,.73):
            a,b=jump_intent(t-1e-7),jump_intent(t+1e-7)
            for field in ('knee_flexion_deg','foot_rise_progress','toe_flexion_deg','flight_clearance'):
                self.assertLess(abs(a[field]-b[field]),.001,(t,field))

    def test_dense_grid_covers_exact_boundaries_and_not_only_pretty_frames(self):
        from jump_chain_v1 import jump_review_times
        times=jump_review_times(True)
        self.assertEqual(times,sorted(set(times)))
        self.assertGreater(len(times),100)
        for t in (.2,.32,.35,.55,.63,.73):
            self.assertIn(t,times);self.assertIn(t-1e-6,times);self.assertIn(t+1e-6,times)

class JumpArticulationEndpointTests(unittest.TestCase):
    def test_ankle_release_and_contact_are_continuous(self):
        self.assertEqual(jump_intent(.35)['ground_push_plantar_deg'],30)
        self.assertAlmostEqual(jump_intent(.35+1e-7)['flight_ankle_plantar_deg'],30)
        self.assertAlmostEqual(jump_intent(.55-1e-7)['flight_ankle_plantar_deg'],25)
        self.assertEqual(jump_intent(.55)['ground_push_plantar_deg'],25)
        self.assertAlmostEqual(jump_intent(.45)['flight_ankle_plantar_deg'],40)

    def test_articulation_stays_in_existing_ankle_working_range(self):
        for i in range(351,550):
            a=jump_intent(i/1000)['flight_ankle_plantar_deg']
            self.assertLessEqual(a,40);self.assertGreaterEqual(a,25)
