import copy
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from port_de_bras_qa import evaluate_port_de_bras  # noqa: E402
from arm_transition import solve_arm_transition  # noqa: E402
import json


def arm(side, lateral, elbow_height, wrist_height, wrist_front):
    sign = 1 if side == "left" else -1
    return {"shoulder": [sign*0.2, 0, 1],
            "elbow": [sign*lateral, -0.1, elbow_height],
            "wrist": [sign*(lateral-0.1), -wrist_front, wrist_height]}


class PortDeBrasQATests(unittest.TestCase):
    def setUp(self):
        self.frame = {"left": [1, 0, 0], "up": [0, 0, 1], "front": [0, -1, 0]}
        self.poses = {}
        for stage, lateral, elbow_up, wrist_up in (("start", 0.45, 0.65, 0.4),
                                                   ("middle", 0.65, 0.75, 0.6),
                                                   ("end", 0.85, 0.8, 0.7)):
            self.poses[stage] = {"arms": {side: arm(side, lateral, elbow_up, wrist_up, 0.2)
                                         for side in ("left", "right")}}

    def test_valid_geometric_relationships_do_not_claim_teacher_approval(self):
        result = evaluate_port_de_bras(self.poses, self.frame)
        self.assertEqual(result["status"], "not_run")
        self.assertFalse(any(c["status"] == "fail" for c in result["checks"]))
        self.assertEqual(next(c for c in result["checks"] if c["name"] == "teacher_approval")["status"], "not_run")

    def test_rejects_fallen_elbow_and_backward_second_position(self):
        poses = copy.deepcopy(self.poses)
        poses["middle"]["arms"]["left"]["elbow"][2] = 0.4
        poses["end"]["arms"]["right"]["wrist"][1] = 0.3
        result = evaluate_port_de_bras(poses, self.frame)
        self.assertEqual(result["status"], "fail")
        failed = {c["name"] for c in result["checks"] if c["status"] == "fail"}
        self.assertIn("left_middle_elbow_line", failed)
        self.assertIn("right_second_position_anterior", failed)

    def test_en_avant_may_draw_wrist_inward_before_second_opens(self):
        # Phase 10 read-only reference: 0.01328 -> 0.00503 -> 0.42547.
        poses = copy.deepcopy(self.poses)
        poses["start"]["arms"]["left"]["wrist"][0] = 0.0132836851
        poses["middle"]["arms"]["left"]["wrist"][0] = 0.0050267937
        poses["end"]["arms"]["left"]["wrist"][0] = 0.4254685164
        check = next(c for c in evaluate_port_de_bras(poses, self.frame)["checks"]
                     if c["name"] == "left_wrist_opens_outward")
        self.assertEqual(check["status"], "pass")

    def test_existing_arm_probe_fails_preparatory_reference(self):
        # Previously keyed arm lift is a geometry probe, never a port de bras.
        spec = json.loads((HERE / "examples/arm_transition_geometry_probe_v0_5.json").read_text())
        calibration = {"rig_profile_id": "low_poly_girl_rig_v0", "source": {"sha256": "a" * 64},
                       "anatomical_frame": self.frame, "canonical_bones": {
                           "left_upper_arm": {"head_local": [0, 0, 0], "rig_bone": "Upper_Arm_L"},
                           "left_forearm": {"head_local": [1, 0, 0], "rig_bone": "Lower_Arm_L"},
                           "left_hand": {"head_local": [2, 0, 0], "rig_bone": "Hand_L"},
                           "right_upper_arm": {"head_local": [0, 0, 0], "rig_bone": "Upper_Arm_R"},
                           "right_forearm": {"head_local": [-1, 0, 0], "rig_bone": "Lower_Arm_R"},
                           "right_hand": {"head_local": [-2, 0, 0], "rig_bone": "Hand_R"}}}
        frames = solve_arm_transition(spec, calibration)["frames"]
        result = evaluate_port_de_bras({"start": frames[0], "middle": frames[8], "end": frames[-1]}, self.frame)
        self.assertEqual(result["status"], "fail")
        self.assertIn("left_preparatory_wrist_inside_elbow", {c["name"] for c in result["checks"] if c["status"] == "fail"})


if __name__ == "__main__":
    unittest.main()
