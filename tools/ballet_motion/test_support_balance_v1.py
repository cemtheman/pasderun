import unittest
from support_balance_v1 import convex_hull, balance_diagnostics


class SupportTests(unittest.TestCase):
    def test_observed_outside_point_cannot_pass(self):
        p={'left':[(0,0),(1,0),(1,1),(0,1)],'right':[]}
        d=balance_diagnostics(p,(1.2,.5),{'left':'SUPPORT','right':'SWING'})
        self.assertEqual(d['status'],'OUTSIDE_SUPPORT')
        self.assertAlmostEqual(d['signed_balance_margin'],-.2)

    def test_swing_geometry_cannot_expand_support(self):
        p={'left':[(0,0),(1,0),(1,1),(0,1)],'right':[(10,0),(11,0),(11,1)]}
        roles={'left':'SUPPORT','right':'SWING'}
        self.assertEqual(balance_diagnostics(p,(5,.5),roles)['status'],'OUTSIDE_SUPPORT')
        roles['right']='SUPPORT'
        self.assertEqual(balance_diagnostics(p,(5,.5),roles)['status'],'PASS')

    def test_order_duplicates_and_boundary(self):
        h=convex_hull([(1,1),(0,0),(.5,.5),(0,1),(1,0),(0,0)])
        self.assertEqual(len(h),4)
        d=balance_diagnostics({'left':h,'right':[]},(0,.5),{'left':'SUPPORT','right':'SWING'})
        self.assertEqual(d['signed_balance_margin'],0)

    def test_degenerate_nonfinite_and_no_support(self):
        for points in ([(0,0),(1,0),(2,0)],[(0,0),(1,float('nan'))]):
            with self.assertRaises(ValueError):convex_hull(points)
        with self.assertRaises(ValueError):balance_diagnostics({},(0,0),{'left':'SWING','right':'SWING'})

if __name__=='__main__':unittest.main()
