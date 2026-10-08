import unittest
from phrase_v1 import phrase_intent,review_times,BOUNDARIES

class PhraseTests(unittest.TestCase):
    def test_closed_endpoints_are_exact(self):
        for style in ('clear','soft'):
            for t in (0,1):
                r=phrase_intent(t,style)
                self.assertEqual((r['plie_coordinate'],r['transfer_coordinate'],r['arm_coordinate']),(0,0,0))
                self.assertEqual(set(r['roles'].values()),{'SUPPORT'})

    def test_bounded_primitives_and_style_overlap(self):
        for style in ('clear','soft'):
            for t in review_times():
                r=phrase_intent(t,style)
                self.assertTrue(0<=r['arm_coordinate']<=1)
                self.assertTrue(0<=r['transfer_coordinate']<=1)
                self.assertTrue(0<=r['plie_coordinate']<=.5)
        r=phrase_intent(.25)
        self.assertGreater(r['transfer_coordinate'],0)
        self.assertGreater(r['arm_coordinate'],.5)
        self.assertNotEqual(phrase_intent(.25,'clear')['arm_coordinate'],phrase_intent(.25,'soft')['arm_coordinate'])

    def test_boundaries_do_not_reset_pose_intent(self):
        for style in ('clear','soft'):
            for t in BOUNDARIES:
                a,b=phrase_intent(t-1e-6,style),phrase_intent(t+1e-6,style)
                for key in ('plie_coordinate','transfer_coordinate','arm_coordinate','head_yaw_deg'):
                    self.assertLess(abs(a[key]-b[key]),1e-4)

    def test_touch_is_contact_not_airborne_and_has_plateau(self):
        for t in (.48,.5,.56):
            r=phrase_intent(t)
            self.assertEqual(r['roles']['right'],'TOUCH')
            self.assertEqual(r['contact_policy'],'FULL_FOOT')
            self.assertEqual(r['transfer_coordinate'],1)

    def test_invalid_inputs_are_rejected(self):
        for t in (-.1,1.1,float('nan'),float('inf')):
            with self.assertRaises(ValueError):phrase_intent(t)
        with self.assertRaises(ValueError):phrase_intent(.5,'unknown')

    def test_dense_grid_requires_neighbours(self):
        ts=review_times()
        for t in BOUNDARIES:
            for d in (-1e-6,0,1e-6):self.assertIn(t+d,ts)
