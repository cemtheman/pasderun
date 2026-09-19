import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools" / "blender" / "build_opening_reverence_v1.py"
WRAPPER = ROOT / "tools" / "blender" / "run_opening_reverence_v1.ps1"


class Phase1044HybridAuthoringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_source_glb_is_immutable_and_outputs_are_new(self) -> None:
        self.assertIn("if input_path == output_path:", self.builder)
        self.assertIn("low_poly_girl_hybrid_arms_v1.glb", self.wrapper)
        self.assertIn(
            "opening_reverence_hybrid_arms_v1_preview.mp4",
            self.wrapper,
        )

    def test_arms_use_explicit_joint_landmarks_not_ik_poles(self) -> None:
        self.assertIn("def create_damped_track_constraint(", self.builder)
        self.assertIn('pb.constraints.new("DAMPED_TRACK")', self.builder)
        self.assertIn('constraint.track_axis = "TRACK_Y"', self.builder)
        self.assertIn('"elbow_side":', self.builder)
        self.assertIn('"wrist_side":', self.builder)
        self.assertIn("arm_elbow_", self.builder)
        self.assertIn("arm_wrist_", self.builder)
        self.assertIn("arm_finish_", self.builder)
        setup = self.builder[
            self.builder.index("def setup_controls_and_constraints("):
            self.builder.index("\n\ndef main()")
        ]
        self.assertNotIn("arm_constraint = create_ik_constraint(", setup)
        self.assertNotIn("arm_pole_", setup)

    def test_leg_native_ik_and_turnout_are_preserved(self) -> None:
        self.assertIn('pb.constraints.new("IK")', self.builder)
        self.assertIn("Phase1044_LegIK_", self.builder)
        self.assertIn("leg_ik_constraints", self.builder)
        self.assertIn("def calibrate_pole_angle(", self.builder)
        self.assertIn("turnout @ foot_world_rotations[suffix]", self.builder)

    def test_arm_landmarks_define_classical_curve(self) -> None:
        for token in (
            '"BRAS_BAS"', '"EN_AVANT"', '"OPEN_HALF"',
            '"ACK_LOW_OPEN"', '"OPEN"', '"LOWERING_SECOND"', '"RESOLVE"',
        ):
            self.assertIn(token, self.builder)
        self.assertIn('"wrist_down": 0.72', self.builder)
        self.assertIn('"elbow_down": 0.42', self.builder)
        self.assertIn('"wrist_forward": 0.35', self.builder)
        self.assertIn('"elbow_forward": 0.22', self.builder)
        self.assertIn('"wrist_side": 0.66', self.builder)
        self.assertIn('"elbow_side": 0.38', self.builder)

    def test_hand_continues_forearm_curve(self) -> None:
        self.assertIn(
            "forearm_tangent = (wrist_target - elbow_target).normalized()",
            self.builder,
        )
        self.assertIn("hand_direction = (", self.builder)
        self.assertIn("inward * 0.10", self.builder)
        self.assertIn("finish_target = (", self.builder)

    def test_authoring_constraints_are_visually_baked_and_removed(self) -> None:
        self.assertIn("bpy.ops.nla.bake", self.builder)
        self.assertIn('"visual_keying": True', self.builder)
        self.assertIn('"clear_constraints": True', self.builder)
        self.assertIn("remove_controls(controls)", self.builder)
        self.assertIn('"leg_native_ik_baked": True', self.builder)
        self.assertIn('"arm_landmark_tracks_baked": True', self.builder)

    def test_reverence_phrase_and_body_wave_are_preserved(self) -> None:
        for token in (
            '"READY_LOW"', '"BRAS_BAS"', '"EN_AVANT_PASSAGE"',
            '"PLACEMENT_AND_SOFTEN"', '"ACKNOWLEDGEMENT"',
            '"RISE_AND_OPEN"', '"LOWERING_SECOND"', '"READY_RESOLUTION"',
        ):
            self.assertIn(token, self.builder)
        self.assertIn('"torso_deg": 9.0', self.builder)
        self.assertIn('"head_deg": 5.0', self.builder)
        self.assertIn('"turnout_deg": 32.0', self.builder)

    def test_blender_52_and_preview_compatibility_remain(self) -> None:
        self.assertIn('bpy.ops.pose.select_all(action="SELECT")', self.builder)
        self.assertIn("def configure_video_output(", self.builder)
        self.assertIn('image_settings.media_type = "VIDEO"', self.builder)
        self.assertIn("if scene.world is None:", self.builder)
        self.assertIn(
            '("BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT")',
            self.builder,
        )

    def test_pipeline_reports_phase_10_4_4(self) -> None:
        self.assertIn('PHASE = "10.4.4"', self.builder)
        self.assertIn("PHASE10_4_4=PASS", self.builder)
        self.assertIn("PHASE 10.4.4 HYBRID AUTHORING PASS", self.wrapper)

    def test_godot_runtime_is_untouched(self) -> None:
        self.assertNotIn("humanoid_motion_controller.gd", self.builder)
        self.assertNotIn("ballerina_visual_v_1.tscn", self.builder)
        self.assertNotIn("build/web", self.wrapper)


if __name__ == "__main__":
    unittest.main()
