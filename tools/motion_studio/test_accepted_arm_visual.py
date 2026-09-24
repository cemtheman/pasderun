import copy
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from accepted_arm_visual import joint_targets  # noqa: E402
from validate import ContractError  # noqa: E402


class AcceptedArmVisualTests(unittest.TestCase):
    def setUp(self):
        self.calibration = {
            "source": {"sha256": "a" * 64},
            "anatomical_frame": {"left": [1, 0, 0], "up": [0, 0, 1], "front": [0, -1, 0]},
            "canonical_bones": {
                "pelvis": {"head_local": [3, 4, 0.5]},
                "head": {"head_local": [3, 4, 2]},
                "left_foot": {"head_local": [3, 4, 0]},
                "right_foot": {"head_local": [3, 4, 0]},
            },
        }
        poses = {}
        for pose in ("bras_bas", "en_avant", "second"):
            joints = {}
            for side, sign in (("left", 1), ("right", -1)):
                for joint, point in (("shoulder", [sign * .1, .5, 0]),
                                     ("elbow", [sign * .2, .5, 0]),
                                     ("wrist", [sign * .3, .5, 0]),
                                     ("hand", [sign * .32, .5, 0])):
                    joints[f"{side}_{joint}"] = point
                for joint, name, offset in (("upper_arm", "Upper_Arm", .2),
                                            ("forearm", "Lower_Arm", .4),
                                            ("hand", "Hand", .6)):
                    self.calibration["canonical_bones"][f"{side}_{joint}"] = {
                        "rig_bone": f"{name}_{side[0].upper()}",
                        "head_local": [3 + sign * offset, 4, 1.5],
                        "length": .04 if joint == "hand" else .2}
            poses[pose] = joints
        self.reference = {"schema_version": "0.6.1", "reference_id": "phase10_6_foundation_arm_landmarks",
                          "source_profile_sha256": "b" * 64, "source_glb_sha256": "a" * 64,
                          "coordinate_space": "body_relative", "position_unit": "standing_height",
                          "poses": poses}

    def test_body_coordinates_reconstruct_calibrated_local_joint_centers(self):
        result = joint_targets(self.reference, self.calibration, "second")
        self.assertEqual(result["arms"]["left"]["shoulder"], [3.2, 4.0, 1.5])
        self.assertEqual(result["arms"]["left"]["elbow"], [3.4, 4.0, 1.5])
        self.assertEqual(result["arms"]["right"]["wrist"], [2.4, 4.0, 1.5])
        self.assertEqual(result["arms"]["left"]["bone_names"], ["Upper_Arm_L", "Lower_Arm_L", "Hand_L"])

    def test_rejects_stale_glb_and_bone_length_mismatch(self):
        old = copy.deepcopy(self.reference)
        old["source_glb_sha256"] = "c" * 64
        with self.assertRaisesRegex(ContractError, "digest mismatch"):
            joint_targets(old, self.calibration, "second")
        old = copy.deepcopy(self.reference)
        old["poses"]["second"]["left_elbow"] = [.22, .5, 0]
        with self.assertRaisesRegex(ContractError, "length"):
            joint_targets(old, self.calibration, "second")

    def test_rejects_hand_target_incompatible_with_measured_hand(self):
        bad = copy.deepcopy(self.reference)
        bad["poses"]["second"]["left_hand"] = [.36, .5, 0]
        with self.assertRaisesRegex(ContractError, "wrist-hand length"):
            joint_targets(bad, self.calibration, "second")


if __name__ == "__main__":
    unittest.main()
