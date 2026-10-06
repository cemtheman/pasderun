import unittest
from bbm_upper_body_v1 import lagged_phase

class PhaseTests(unittest.TestCase):
    def test_endpoints_and_monotonicity(self):
        for lag in (0,.035,.06,.1,.15):
            values=[lagged_phase(i/1000,lag) for i in range(1001)]
            self.assertEqual(values[0],0)
            self.assertAlmostEqual(values[-1],1)
            self.assertTrue(all(a<=b for a,b in zip(values,values[1:])))
            self.assertTrue(all(0<=x<=1 for x in values))
    def test_bad_phases_rejected(self):
        for t,lag in ((float('nan'),0),(.5,float('inf')),(-.1,.1),(.5,.16)):
            with self.assertRaises(ValueError):lagged_phase(t,lag)
    def test_chain_does_not_move_in_robotic_unison(self):
        self.assertGreater(lagged_phase(.5,.035),lagged_phase(.5,.06))
        self.assertGreater(lagged_phase(.5,.06),lagged_phase(.5,.1))
