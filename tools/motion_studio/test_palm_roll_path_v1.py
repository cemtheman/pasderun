import math
import unittest
from palm_roll_path_v1 import select_roll_path


def node(angle,error):
    t=math.radians(angle)/2
    return {'quaternion':(math.cos(t),0,0,math.sin(t)), 'palm_error_rad':error}


class RollPathTests(unittest.TestCase):
    def test_future_feasibility_overrides_local_best(self):
        layers=[[node(0,0),node(60,.2)],[node(65,0)],[node(70,0)]]
        self.assertEqual(select_roll_path(layers),[1,0,0])

    def test_unreachable_path_is_rejected_without_relaxing_bound(self):
        with self.assertRaisesRegex(ValueError,'sample 2'):
            select_roll_path([[node(0,0)],[node(21,0)]])

    def test_quaternion_sign_does_not_create_rotation(self):
        n=node(5,0);opposite={**n,'quaternion':tuple(-v for v in n['quaternion'])}
        self.assertEqual(select_roll_path([[n],[opposite]]),[0,0])

    def test_invalid_inputs_rejected(self):
        for layers in ([],[[]],[[{'quaternion':(2,0,0,0),'palm_error_rad':0}]],[[node(0,float('nan'))]]):
            with self.assertRaises(ValueError):select_roll_path(layers)
        with self.assertRaises(ValueError):select_roll_path([[node(0,0)]],31)
