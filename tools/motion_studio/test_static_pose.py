import copy
import json
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from static_pose import solve_static_pose, solve_two_link  # noqa: E402
from validate import ContractError  # noqa: E402


class StaticPoseGeometryTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((HERE / "examples/arm_reach_geometry_probe_v0_3.json").read_text(encoding="utf-8"))
        self.calibration = {
            "rig_profile_id": "low_poly_girl_rig_v0", "source": {"sha256": "a" * 64},
            "anatomical_frame": {"left": [1, 0, 0], "up": [0, 0, 1], "front": [0, -1, 0]},
            "canonical_bones": {
                "left_upper_arm": {"head_local": [0, 0, 0], "rig_bone": "Upper_Arm_L"},
                "left_forearm": {"head_local": [1, 0, 0], "rig_bone": "Lower_Arm_L"},
                "left_hand": {"head_local": [2, 0, 0], "rig_bone": "Hand_L"},
                "right_upper_arm": {"head_local": [0, 0, 0], "rig_bone": "Upper_Arm_R"},
                "right_forearm": {"head_local": [-1, 0, 0], "rig_bone": "Lower_Arm_R"},
                "right_hand": {"head_local": [-2, 0, 0], "rig_bone": "Hand_R"},
            },
        }

    def test_symmetric_arm_targets_keep_lengths_and_downward_bend(self):
        result = solve_static_pose(self.spec, self.calibration)
        left, right = result["arms"]["left"], result["arms"]["right"]
        self.assertEqual(left["wrist"], [1.9, -0.04, 0.0])
        self.assertEqual(right["wrist"], [-1.9, -0.04, 0.0])
        self.assertAlmostEqual(left["upper_length"], 1)
        self.assertAlmostEqual(left["lower_length"], 1)
        self.assertGreater(left["bend_plane_projection"], 0)
        self.assertGreater(right["bend_plane_projection"], 0)
        self.assertAlmostEqual(left["elbow"][0], -right["elbow"][0])
        self.assertAlmostEqual(left["elbow"][1], right["elbow"][1])
        self.assertLess(left["elbow"][2], 0)
        self.assertLess(right["elbow"][2], 0)

    def test_asymmetric_lengths_are_preserved(self):
        solved = solve_two_link([0, 0, 0], [2, 0, 0], [3, 0, 0], [2, 0.5, 0], [0, 1, 0])
        self.assertAlmostEqual(solved["upper_length"], 2)
        self.assertAlmostEqual(solved["lower_length"], 1)

    def test_unreachable_and_pole_singular_are_explicit_failures(self):
        with self.assertRaisesRegex(ContractError, "unreachable"):
            solve_two_link([0, 0, 0], [1, 0, 0], [2, 0, 0], [2.1, 0, 0], [0, 1, 0])
        with self.assertRaisesRegex(ContractError, "degenerate vector"):
            solve_two_link([0, 0, 0], [1, 0, 0], [2, 0, 0], [1.5, 0, 0], [1, 0, 0])

    def test_invalid_target_identity_and_schema(self):
        spec = copy.deepcopy(self.spec)
        spec["targets"][0]["landmark"] = "right_wrist"
        with self.assertRaisesRegex(ContractError, "landmark and side"):
            solve_static_pose(spec, self.calibration)
        spec = copy.deepcopy(self.spec)
        spec["targets"][1]["side"] = "left"
        spec["targets"][1]["landmark"] = "left_wrist"
        with self.assertRaisesRegex(ContractError, "duplicate arm"):
            solve_static_pose(spec, self.calibration)
        spec = copy.deepcopy(self.spec)
        spec["schema_version"] = "0.4.0"
        with self.assertRaises(ContractError):
            solve_static_pose(spec, self.calibration)


if __name__ == "__main__":
    unittest.main()
