import json
import pathlib
import unittest

from ballet_pose_validators import validate_pose


ROOT = pathlib.Path(__file__).resolve().parents[2]
GRAMMAR = ROOT / "assets" / "ballet_motion" / "ballet_pose_grammar_v1.json"
FIXTURES = ROOT / "assets" / "ballet_motion" / "ballet_pose_fixtures_v1.json"
BUILDER = ROOT / "tools" / "ballet_motion" / "build_ballet_pose_grammar_profile_v1.py"
WRAPPER = ROOT / "tools" / "ballet_motion" / "run_phase10_6_4_ballet_pose_grammar.ps1"


class Phase1064BalletPoseGrammarTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.grammar = json.loads(GRAMMAR.read_text(encoding="utf-8"))
        cls.fixtures = json.loads(FIXTURES.read_text(encoding="utf-8"))
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_exact_required_pose_vocabulary(self) -> None:
        self.assertEqual(
            set(self.grammar["poses"]),
            {"bras_bas", "en_avant", "second", "fifth", "plie", "releve"},
        )

    def test_anterior_is_positive_front_and_never_inferred(self) -> None:
        contract = self.grammar["coordinate_contract"]
        self.assertEqual(contract["anterior_means"], "front > 0")
        self.assertEqual(
            contract["body_front_source"],
            "DECLARED_BY_RIG_CALIBRATION_ONLY",
        )

    def test_bras_bas_requires_all_arm_landmarks_in_front(self) -> None:
        checks = self.grammar["poses"]["bras_bas"]["checks"]
        anterior = next(item for item in checks if item["type"] == "anterior_halfspace")
        self.assertIn("left_elbow", anterior["landmarks"])
        self.assertIn("right_elbow", anterior["landmarks"])
        self.assertIn("left_wrist", anterior["landmarks"])
        self.assertIn("right_wrist", anterior["landmarks"])
        self.assertIn("left_hand", anterior["landmarks"])
        self.assertIn("right_hand", anterior["landmarks"])
        self.assertGreater(anterior["min_front"], 0.0)

    def test_arms_behind_back_regression_is_explicit(self) -> None:
        fixture = self.fixtures["fixtures"]["bras_bas_arms_behind_back"]
        self.assertEqual(fixture["expected"], "FAIL")
        self.assertEqual(
            fixture["expected_failed_validator"],
            "anterior_halfspace",
        )
        for name in ("left_elbow", "right_elbow", "left_wrist", "right_wrist"):
            self.assertLess(fixture["landmarks"][name]["front"], 0.0)

    def test_second_position_explicitly_prevents_locked_t_pose(self) -> None:
        checks = self.grammar["poses"]["second"]["checks"]
        elbow = next(item for item in checks if item["type"] == "elbow_angle_range")
        self.assertLess(elbow["max_deg"], 180)
        self.assertIn(
            "wrist_below_shoulder",
            {item["type"] for item in checks},
        )

    def test_fifth_is_contact_turnout_balance_and_closure(self) -> None:
        kinds = {item["type"] for item in self.grammar["poses"]["fifth"]["checks"]}
        self.assertTrue(
            {"contact_mode", "fifth_closure", "turnout_chain", "support_polygon_com"}
            <= kinds
        )

    def test_plie_requires_knee_tracking_and_full_foot_contact(self) -> None:
        checks = self.grammar["poses"]["plie"]["checks"]
        kinds = {item["type"] for item in checks}
        self.assertIn("knee_second_toe_tracking", kinds)
        contact = next(item for item in checks if item["type"] == "contact_mode")
        self.assertEqual(contact["left"], "FULL_FOOT")
        self.assertEqual(contact["right"], "FULL_FOOT")

    def test_releve_requires_forefoot_contact_and_heel_height(self) -> None:
        checks = self.grammar["poses"]["releve"]["checks"]
        contact = next(item for item in checks if item["type"] == "contact_mode")
        self.assertEqual(contact["left"], "FOREFOOT")
        self.assertEqual(contact["right"], "FOREFOOT")
        scalars = [item["name"] for item in checks if item["type"] == "scalar_range"]
        self.assertIn("left_heel_height", scalars)
        self.assertIn("right_heel_height", scalars)

    def test_invalid_geometry_blocks_render_and_animation(self) -> None:
        policy = self.grammar["policy"]
        self.assertTrue(policy["failed_geometric_validator_blocks_render"])
        self.assertTrue(policy["failed_geometric_validator_blocks_animation"])
        self.assertIn("ARMS_BEHIND_BACK=BLOCKED", self.builder)

    def test_wrapper_auto_generates_10_6_3_prerequisite(self) -> None:
        self.assertIn(
            "run_phase10_6_3_anatomical_constraints.ps1",
            self.wrapper,
        )
        self.assertIn("generating prerequisite", self.wrapper)

    def test_wrapper_is_ascii_safe_for_windows_powershell(self) -> None:
        self.assertTrue(all(ord(char) < 128 for char in self.wrapper))

    def test_builder_has_no_blender_or_godot_motion_scope(self) -> None:
        self.assertNotIn("import bpy", self.builder)
        self.assertNotIn("Skeleton3D", self.builder)
        self.assertNotIn("AnimationTree", self.builder)
        self.assertIn(
            "No Blender runtime. No render. No pose synthesis. No animation.",
            self.wrapper,
        )

    def test_output_contract_is_phase_10_6_4(self) -> None:
        self.assertIn('PHASE = "10.6.4"', self.builder)
        self.assertIn("PHASE10_6_4_BALLET_POSE_GRAMMAR=PASS", self.builder)
        self.assertIn(
            "low_poly_girl_ballet_pose_grammar_profile_v1.json",
            self.wrapper,
        )


if __name__ == "__main__":
    unittest.main()
