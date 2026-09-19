import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools" / "blender" / "build_opening_reverence_v1.py"
WRAPPER = ROOT / "tools" / "blender" / "run_opening_reverence_v1.ps1"


class Phase1045RollStableArmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_source_is_immutable_and_outputs_are_new(self) -> None:
        self.assertIn("if input_path == output_path:", self.builder)
        self.assertIn("low_poly_girl_rollstable_arms_v1.glb", self.wrapper)
        self.assertIn(
            "opening_reverence_rollstable_arms_v1_preview.mp4",
            self.wrapper,
        )

    def test_arms_use_direct_roll_stable_frames(self) -> None:
        self.assertIn("def choose_roll_axis(", self.builder)
        self.assertIn("def set_roll_stable_bone_frame(", self.builder)
        self.assertIn("def apply_arm_landmark_pose(", self.builder)
        self.assertIn("def key_arm_landmark_pose(", self.builder)
        self.assertIn('roll_axis == "Z"', self.builder)
        self.assertIn(
            "basis = Matrix((x_axis, y_axis, z_axis)).transposed()",
            self.builder,
        )

    def test_arm_constraints_are_removed_from_authoring_model(self) -> None:
        self.assertNotIn('pb.constraints.new("DAMPED_TRACK")', self.builder)
        self.assertNotIn("create_damped_track_constraint(", self.builder)
        setup = self.builder[
            self.builder.index("def setup_leg_controls_and_constraints("):
            self.builder.index("\n\ndef main()")
        ]
        self.assertNotIn("arm_", setup)

    def test_ballet_plane_controls_arm_roll(self) -> None:
        self.assertIn("plane_normal = upper_direction.cross(forearm_direction)", self.builder)
        self.assertIn("reference_normal = (forward * side_sign).normalized()", self.builder)
        self.assertIn("normal.dot(reference_normal) < 0.0", self.builder)
        self.assertIn("choose_roll_axis(", self.builder)

    def test_explicit_elbow_wrist_hand_landmarks_remain(self) -> None:
        self.assertIn("elbow_target = (", self.builder)
        self.assertIn("wrist_target = (", self.builder)
        self.assertIn("finish_target = (", self.builder)
        self.assertIn('"wrist_down": 0.72', self.builder)
        self.assertIn('"wrist_forward": 0.35', self.builder)
        self.assertIn('"wrist_side": 0.66', self.builder)

    def test_leg_native_ik_and_turnout_are_preserved(self) -> None:
        self.assertIn('pb.constraints.new("IK")', self.builder)
        self.assertIn("Phase1045_LegIK_", self.builder)
        self.assertIn("def calibrate_pole_angle(", self.builder)
        self.assertIn("turnout @ foot_world_rotations[suffix]", self.builder)

    def test_combined_motion_is_visually_baked_and_cleaned(self) -> None:
        self.assertIn("def bake_authoring_constraints(", self.builder)
        self.assertIn('"visual_keying": True', self.builder)
        self.assertIn('"clear_constraints": True', self.builder)
        self.assertIn("remove_controls(controls)", self.builder)
        self.assertIn('"leg_native_ik_baked": True', self.builder)
        self.assertIn('"arm_roll_stable_frames_baked": True', self.builder)
        self.assertIn(
            'obj.name.startswith(("P1043_", "P1044_", "P1045_"))',
            self.builder,
        )

    def test_body_wave_cross_and_turnout_are_preserved(self) -> None:
        self.assertIn('"torso_deg": 9.0', self.builder)
        self.assertIn('"head_deg": 5.0', self.builder)
        self.assertIn('"turnout_deg": 32.0', self.builder)
        self.assertIn("ankle += side * hip_width * 1.75 * cross", self.builder)

    def test_blender_52_preview_compatibility_is_preserved(self) -> None:
        self.assertIn('bpy.ops.pose.select_all(action="SELECT")', self.builder)
        self.assertIn('image_settings.media_type = "VIDEO"', self.builder)
        self.assertIn("if scene.world is None:", self.builder)
        self.assertIn(
            '("BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT")',
            self.builder,
        )

    def test_phase_and_runtime_scope(self) -> None:
        self.assertIn('PHASE = "10.4.5"', self.builder)
        self.assertIn("PHASE10_4_5=PASS", self.builder)
        self.assertIn("PHASE 10.4.5 ROLL-STABLE ARMS PASS", self.wrapper)
        self.assertNotIn("humanoid_motion_controller.gd", self.builder)
        self.assertNotIn("ballerina_visual_v_1.tscn", self.builder)
        self.assertNotIn("build/web", self.wrapper)


if __name__ == "__main__":
    unittest.main()
