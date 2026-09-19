import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
BUILDER = ROOT / "tools" / "blender" / "build_opening_reverence_v1.py"
WRAPPER = ROOT / "tools" / "blender" / "run_opening_reverence_v1.ps1"


class Phase104NativeIKPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_source_glb_is_immutable_and_outputs_are_versioned(self) -> None:
        self.assertIn('if input_path == output_path:', self.builder)
        self.assertIn(
            'raise RuntimeError("Refusing to overwrite the source GLB.")',
            self.builder,
        )
        self.assertIn(
            'low_poly_girl_native_ik_v1.glb',
            self.wrapper,
        )
        self.assertIn(
            'opening_reverence_native_ik_v1_preview.mp4',
            self.wrapper,
        )

    def test_native_ik_replaces_custom_two_bone_authoring(self) -> None:
        self.assertIn('pb.constraints.new("IK")', self.builder)
        self.assertIn('constraint.chain_count = 2', self.builder)
        self.assertIn('constraint.pole_target = pole', self.builder)
        self.assertIn('constraint.use_stretch = False', self.builder)
        self.assertNotIn('def solve_two_bone_joint(', self.builder)
        self.assertNotIn('def aim_parent_to_child(', self.builder)

    def test_controls_are_initialized_before_ik_constraints(self) -> None:
        self.assertIn(
            "Capture clean rest orientations before any constraint can evaluate.",
            self.builder,
        )
        self.assertIn(
            "Put every control on the current limb before adding IK.",
            self.builder,
        )
        setup_start = self.builder.index("def setup_controls_and_constraints(")
        setup_end = self.builder.index("\n\ndef main()", setup_start)
        setup = self.builder[setup_start:setup_end]
        first_target = setup.index('set_control_location(\n            controls[f"arm_target_{suffix}"]')
        first_constraint = setup.index("arm_constraint = create_ik_constraint(")
        self.assertLess(first_target, first_constraint)

    def test_pole_angle_is_calibrated_from_evaluated_rig(self) -> None:
        self.assertIn('def calibrate_pole_angle(', self.builder)
        self.assertIn('pole_alignment_score(', self.builder)
        self.assertIn('constraint.pole_angle = best_angle', self.builder)
        self.assertIn('"pole_angles_deg": pole_angles', self.builder)

    def test_blender_52_pose_selection_uses_operator_api(self) -> None:
        self.assertIn('bpy.ops.pose.select_all(action="SELECT")', self.builder)
        self.assertIn('bpy.ops.object.select_all(action="DESELECT")', self.builder)
        self.assertNotIn('.select = True', self.builder)

    def test_native_ik_is_visually_baked_and_cleaned(self) -> None:
        self.assertIn('bpy.ops.nla.bake', self.builder)
        self.assertIn('"visual_keying": True', self.builder)
        self.assertIn('"clear_constraints": True', self.builder)
        self.assertIn('remove_controls(controls)', self.builder)
        self.assertIn('"constraints_after_bake": remaining_constraints', self.builder)
        self.assertIn('"temporary_controls_after_bake": remaining_controls', self.builder)

    def test_phrase_starts_at_frame_zero_and_keeps_reference_landmarks(self) -> None:
        self.assertIn('START_FRAME = 0', self.builder)
        self.assertIn('END_FRAME = 67', self.builder)
        for token in (
            '"READY_LOW"', '"BRAS_BAS"', '"EN_AVANT_PASSAGE"',
            '"PLACEMENT_AND_SOFTEN"', '"ACKNOWLEDGEMENT"',
            '"RISE_AND_OPEN"', '"READY_RESOLUTION"',
        ):
            self.assertIn(token, self.builder)

    def test_feet_are_world_oriented_during_leg_ik(self) -> None:
        self.assertIn('pb.constraints.new("COPY_ROTATION")', self.builder)
        self.assertIn('constraint.target_space = "WORLD"', self.builder)
        self.assertIn('constraint.owner_space = "WORLD"', self.builder)
        self.assertIn('constraint.mix_mode = "REPLACE"', self.builder)

    def test_baked_action_preserves_visual_samples(self) -> None:
        self.assertIn(
            "Native IK has already been evaluated and visually sampled every frame.",
            self.builder,
        )
        self.assertIn('point.interpolation = "LINEAR"', self.builder)

    def test_preview_engine_is_runtime_compatible(self) -> None:
        self.assertIn("def choose_preview_engine(", self.builder)
        self.assertIn('"BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"', self.builder)
        self.assertIn('scene.render.bl_rna.properties["engine"]', self.builder)
        self.assertIn('"preview_engine": preview_engine', self.builder)
        self.assertNotIn('scene.render.engine = "BLENDER_EEVEE_NEXT"', self.builder)

    def test_preview_is_rendered_automatically(self) -> None:
        self.assertIn('scene.render.engine = "BLENDER_EEVEE_NEXT"', self.builder)
        self.assertIn('scene.render.image_settings.file_format = "FFMPEG"', self.builder)
        self.assertIn('scene.render.ffmpeg.codec = "H264"', self.builder)
        self.assertIn('bpy.ops.render.render(animation=True)', self.builder)
        self.assertIn('PHASE 10.4.3 NATIVE IK PASS', self.wrapper)

    def test_godot_runtime_is_not_part_of_authoring_pipeline(self) -> None:
        self.assertNotIn('humanoid_motion_controller.gd', self.builder)
        self.assertNotIn('ballerina_visual_v_1.tscn', self.builder)
        self.assertNotIn('build/web', self.wrapper)


if __name__ == "__main__":
    unittest.main()
