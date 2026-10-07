import json,unittest
from pathlib import Path
from foot_semantics_v1 import foot_state,anatomical_plantar_from_canonical
C=json.loads((Path(__file__).resolve().parents[2]/'assets/ballet_motion/anatomical_constraints_v1.json').read_text())
class FootTests(unittest.TestCase):
    def test_support_role_changes_without_free_yaw(self):
        flat=foot_state(C,'FLAT',0,0);demi=foot_state(C,'DEMI_POINTE',35,50);ready=foot_state(C,'POINTE_READY',50,0)
        self.assertEqual(len({s['support_region'] for s in (flat,demi,ready)}),3)
        self.assertTrue(all(s['independent_foot_yaw_deg']==0 for s in (flat,demi,ready)))
        self.assertFalse(ready['full_en_pointe_claim'])
    def test_preferred_envelope_is_not_expanded_for_pointe(self):
        with self.assertRaises(ValueError):foot_state(C,'POINTE_READY',51,0)
    def test_unobservable_arch_is_semantic(self):
        self.assertFalse(foot_state(C,'DEMI_POINTE',35,50)['independent_arch_bone'])
    def test_invalid_input_is_rejected(self):
        for state,angle in [('UNKNOWN',0),('FLAT',float('nan'))]:
            with self.assertRaises(ValueError):foot_state(C,state,angle,0)

    def test_neutral_reference_preserves_anatomical_boundary(self):
        self.assertEqual(anatomical_plantar_from_canonical(C,82.377,32.377)['status'],'PASS')
        self.assertEqual(anatomical_plantar_from_canonical(C,83.377,32.377)['status'],'SOFT_LIMIT')
        self.assertEqual(anatomical_plantar_from_canonical(C,93.377,32.377)['status'],'HARD_LIMIT')
        self.assertAlmostEqual(anatomical_plantar_from_canonical(C,32.377,32.377)['anatomical_plantar_deg'],0)
