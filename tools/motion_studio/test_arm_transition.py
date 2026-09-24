import copy
import json
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from arm_transition import solve_arm_transition  # noqa: E402
from static_pose import solve_static_pose  # noqa: E402
from validate import ContractError  # noqa: E402


class ArmTransitionTests(unittest.TestCase):
    def setUp(self):
        self.spec = json.loads((HERE / "examples/arm_transition_geometry_probe_v0_5.json").read_text())
        self.calibration = {"rig_profile_id": "low_poly_girl_rig_v0", "source": {"sha256": "a" * 64},
                            "anatomical_frame": {"left": [1, 0, 0], "up": [0, 0, 1], "front": [0, -1, 0]},
                            "canonical_bones": {
                                "left_upper_arm": {"head_local": [0, 0, 0], "rig_bone": "Upper_Arm_L"},
                                "left_forearm": {"head_local": [1, 0, 0], "rig_bone": "Lower_Arm_L"},
                                "left_hand": {"head_local": [2, 0, 0], "rig_bone": "Hand_L"},
                                "right_upper_arm": {"head_local": [0, 0, 0], "rig_bone": "Upper_Arm_R"},
                                "right_forearm": {"head_local": [-1, 0, 0], "rig_bone": "Lower_Arm_R"},
                                "right_hand": {"head_local": [-2, 0, 0], "rig_bone": "Hand_R"}}}

    def test_solved_endpoints_and_smooth_wrist_path(self):
        result = solve_arm_transition(self.spec, self.calibration)
        self.assertEqual(len(result["frames"]), 17)
        start = solve_static_pose(self.spec["start_pose"], self.calibration)
        end = solve_static_pose(self.spec["end_pose"], self.calibration)
        for side in ("left", "right"):
            self.assertEqual(result["frames"][0]["arms"][side]["wrist"], start["arms"][side]["wrist"])
            self.assertEqual(result["frames"][-1]["arms"][side]["wrist"], end["arms"][side]["wrist"])
            heights = [f["arms"][side]["wrist"][2] for f in result["frames"]]
            self.assertEqual(heights, sorted(heights))
            self.assertLess(heights[1] - heights[0], heights[8] - heights[7])
            self.assertLess(heights[-1] - heights[-2], heights[8] - heights[7])

    def test_rejects_unmatched_arms_poles_and_bad_version(self):
        spec = copy.deepcopy(self.spec)
        spec["end_pose"]["targets"].pop()
        with self.assertRaisesRegex(ContractError, "arm sides differ"):
            solve_arm_transition(spec, self.calibration)
        spec = copy.deepcopy(self.spec)
        spec["end_pose"]["targets"][0]["bend_plane"] = "body_up"
        with self.assertRaisesRegex(ContractError, "bend plane changes"):
            solve_arm_transition(spec, self.calibration)
        spec = copy.deepcopy(self.spec)
        spec["schema_version"] = "0.6.0"
        with self.assertRaisesRegex(ContractError, "wrong constant"):
            solve_arm_transition(spec, self.calibration)


if __name__ == "__main__":
    unittest.main()
