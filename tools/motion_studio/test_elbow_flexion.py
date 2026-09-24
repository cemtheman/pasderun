import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from elbow_flexion import inward_flexion  # noqa: E402
from validate import ContractError  # noqa: E402


class ElbowFlexionTests(unittest.TestCase):
    def test_bend_is_measured_relative_to_upper_arm(self):
        pose = {"shoulder": [0, 0, 0], "elbow": [1, 0, 0], "wrist": [1.8, -.2, 0]}
        result = inward_flexion(pose, [-1, -.3, 0], "left")
        self.assertGreater(result["signed_inward_alignment"], 0)
        # Rotate the entire construction by a quarter-turn around Z; the
        # same elbow still flexes toward the rotated anatomical inward cue.
        rotate = lambda v: [-v[1], v[0], v[2]]
        rotated = {name: rotate(point) for name, point in pose.items()}
        self.assertAlmostEqual(result["signed_inward_alignment"],
                               inward_flexion(rotated, rotate([-1, -.3, 0]), "left")
                               ["signed_inward_alignment"])

    def test_outward_and_singular_bends_are_rejected(self):
        base = {"shoulder": [0, 0, 0], "elbow": [1, 0, 0]}
        with self.assertRaisesRegex(ContractError, "flexes outward"):
            inward_flexion({**base, "wrist": [1.8, .2, 0]}, [0, -1, 0], "left")
        with self.assertRaisesRegex(ContractError, "singularly straight"):
            inward_flexion({**base, "wrist": [1.8, 0, 0]}, [0, -1, 0], "left")


if __name__ == "__main__":
    unittest.main()
