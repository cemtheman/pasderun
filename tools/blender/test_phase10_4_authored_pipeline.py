import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools" / "blender" / "build_opening_reverence_v1.py"
WRAPPER = ROOT / "tools" / "blender" / "run_opening_reverence_v1.ps1"


class Phase104AuthoredPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_source_glb_is_never_overwritten(self) -> None:
        self.assertIn('if input_path == output_path:', self.builder)
        self.assertIn('raise RuntimeError("Refusing to overwrite the source GLB.")', self.builder)
        self.assertIn('build\\phase10_4\\low_poly_girl_authored_v3.glb', self.wrapper)

    def test_rig_aware_authoring_replaces_guessed_eulers(self) -> None:
        self.assertIn("def canonical_axes(", self.builder)
        self.assertIn("def aim_parent_to_child(", self.builder)
        self.assertIn("def solve_two_bone_joint(", self.builder)
        self.assertIn("rotation_difference(desired.normalized())", self.builder)
        self.assertNotIn("from mathutils import Euler", self.builder)
        self.assertNotIn("def set_rotation_deg(", self.builder)
        self.assertNotIn('"rot": {', self.builder)

    def test_reverence_phrase_has_reference_landmarks(self) -> None:
        for token in (
            '"READY_LOW"', '"BRAS_BAS"', '"EN_AVANT_PASSAGE"',
            '"PLACEMENT_AND_SOFTEN"', '"ACKNOWLEDGEMENT"',
            '"RISE_AND_OPEN"', '"READY_RESOLUTION"',
            '"arm_shape": "EN_AVANT"',
            '"arm_shape": "OPEN_HALF"',
            '"arm_shape": "OPEN"',
        ):
            self.assertIn(token, self.builder)

    def test_leg_chain_is_placement_first_without_explicit_knee_out(self) -> None:
        self.assertIn("ankle_target += side * hip_width * 1.05 * cross", self.builder)
        self.assertIn("forward * 0.78", self.builder)
        self.assertIn("side * side_sign * 0.35", self.builder)
        self.assertIn("solve_two_bone_joint(", self.builder)
        self.assertIn("turnout_direction = (", self.builder)
        self.assertNotIn("knee_outward", self.builder)
        self.assertNotIn("knee_target +=", self.builder)

    def test_open_arm_elbow_hint_is_not_outward_collinear(self) -> None:
        self.assertIn('"elbow_side": 0.46, "elbow_forward": 0.30, "elbow_down": 0.10', self.builder)
        self.assertIn("The elbow hint is deliberately not collinear with the hand target.", self.builder)
        self.assertNotIn('"pole_side":', self.builder)

    def test_hand_continues_forearm_tangent(self) -> None:
        self.assertIn("tangent = (hand_head - elbow_head).normalized()", self.builder)
        self.assertIn("finish_direction = (", self.builder)
        self.assertIn("aim_parent_to_child(", self.builder)
        self.assertNotIn("hand_finish_direction", self.builder)

    def test_pipeline_reports_geometry_and_validation_error(self) -> None:
        self.assertIn('"authoring_model": "rig-aware joint targets + two-bone solve"', self.builder)
        self.assertIn('"canonical_axes":', self.builder)
        self.assertIn('"max_aim_error":', self.builder)
        self.assertIn('"landmarks": capture_landmarks(armature)', self.builder)
        self.assertIn("PHASE 10.4.2.1 PIPELINE PASS", self.wrapper)


if __name__ == "__main__":
    unittest.main()
