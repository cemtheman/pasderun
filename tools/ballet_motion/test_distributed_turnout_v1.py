import json,math,unittest
from pathlib import Path
from distributed_turnout_v1 import derive_turnout,alignment_diagnostics

C=json.loads((Path(__file__).resolve().parents[2]/'assets/ballet_motion/anatomical_constraints_v1.json').read_text())
class TurnoutTests(unittest.TestCase):
    def test_hip_primary_and_flexion_dependent_knee(self):
        straight=derive_turnout(C,45,0);bent=derive_turnout(C,45,60)
        self.assertEqual(straight['independent_foot_yaw_deg'],0)
        self.assertLess(straight['knee_external_rotation_deg'],bent['knee_external_rotation_deg'])
        self.assertLessEqual(bent['knee_external_rotation_deg'],bent['knee_external_rotation_cap_deg'])
        self.assertEqual(derive_turnout(C,0,60)['knee_external_rotation_deg'],0)
    def test_excess_hip_request_is_not_silently_clamped(self):
        self.assertEqual(derive_turnout(C,81,0)['status'],'HARD_LIMIT')
    def test_observed_bad_tracking_cannot_be_hidden_by_authored_zero(self):
        r=alignment_diagnostics(C,(0,1,0),(math.sin(math.radians(20)),math.cos(math.radians(20)),0),(0,1,0),(0,0,1))
        self.assertEqual(r['status'],'HARD_LIMIT');self.assertAlmostEqual(r['observed_knee_toe_error_deg'],20)
    def test_degenerate_projection_and_nonfinite_input_rejected(self):
        with self.assertRaises(ValueError):alignment_diagnostics(C,(0,0,1),(0,1,0),(0,1,0),(0,0,1))
        with self.assertRaises(ValueError):derive_turnout(C,float('nan'),0)
