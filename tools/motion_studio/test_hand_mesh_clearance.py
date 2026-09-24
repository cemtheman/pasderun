import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hand_mesh_clearance import frontal_hand_gap  # noqa: E402
from validate import ContractError  # noqa: E402


class HandMeshClearanceTests(unittest.TestCase):
    def test_projected_gap_uses_inner_edges_of_both_hands(self):
        clear = {"left": [[.1, 0, 0], [.3, 0, 0]],
                 "right": [[-.3, 0, 0], [-.1, 0, 0]]}
        self.assertAlmostEqual(frontal_hand_gap(clear, [1, 0, 0])["projected_gap_armature_units"], .2)
        crossing = {"left": [[-.04, 0, 0], [.3, 0, 0]],
                    "right": [[-.3, 0, 0], [.03, 0, 0]]}
        self.assertAlmostEqual(frontal_hand_gap(crossing, [1, 0, 0])["projected_gap_armature_units"], -.07)

    def test_rejects_missing_mesh_sample(self):
        with self.assertRaisesRegex(ContractError, "both sides"):
            frontal_hand_gap({"left": [], "right": [[0, 0, 0]]}, [1, 0, 0])


if __name__ == "__main__":
    unittest.main()
