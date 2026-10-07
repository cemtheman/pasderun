import unittest
from weight_transfer_v1 import transfer_intent,weightbearing_roles
from support_balance_v1 import balance_diagnostics
class TransferTests(unittest.TestCase):
    def test_touch_preserves_contact_without_expanding_support(self):
        intent=transfer_intent(1);self.assertEqual(intent['contacts']['right'],'FULL_FOOT')
        p={'left':[(0,0),(1,0),(1,1),(0,1)],'right':[(10,0),(11,0),(11,1)]}
        self.assertEqual(balance_diagnostics(p,(5,.5),weightbearing_roles(intent['contact_roles']))['status'],'OUTSIDE_SUPPORT')
    def test_bounded_exact_intent_and_invalid_time(self):
        self.assertEqual(transfer_intent(0)['pelvis_left_displacement'],0);self.assertEqual(transfer_intent(1)['pelvis_left_displacement'],.08)
        self.assertTrue(all(0<=transfer_intent(i/100)['pelvis_left_displacement']<=.08 for i in range(101)))
        for t in (-.1,float('nan')):
            with self.assertRaises(ValueError):transfer_intent(t)
    def test_no_weightbearing_role_rejected(self):
        with self.assertRaises(ValueError):weightbearing_roles({'left':'TOUCH','right':'TOUCH'})

    def test_rotation_double_cover_and_real_jump(self):
        import math
        from weight_transfer_v1 import rotation_step_degrees
        self.assertEqual(rotation_step_degrees((1,0,0,0),(-1,0,0,0)),0)
        q=(math.cos(math.radians(31)/2),math.sin(math.radians(31)/2),0,0)
        self.assertAlmostEqual(rotation_step_degrees((1,0,0,0),q),31)
        self.assertGreater(rotation_step_degrees((1,0,0,0),q),30)
        with self.assertRaises(ValueError):rotation_step_degrees((0,0,0,0),q)
