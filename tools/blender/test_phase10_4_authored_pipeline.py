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
            'low_poly_girl_native_ik_v3.glb',
            self.wrapper,
        )
        self.assertIn(
            'opening_reverence_native_ik_v3_preview.mp4',
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

    def test_arm_shapes_are_applied_from_shoulder_center(self) -> None:
        self.assertIn("shoulder_center = (", self.builder)
        self.assertIn("hand_target = (\n        shoulder_center", self.builder)
        self.assertIn("double-counts shoulder width", self.builder)

    def test_classical_arm_shapes_are_rounded_and_lowered(self) -> None:
        self.assertIn('"hand_down": 0.68', self.builder)
        self.assertIn('"hand_down": 0.26', self.builder)
        self.assertIn('"hand_side": 0.72', self.builder)
        self.assertIn('"ACK_LOW_OPEN"', self.builder)
        self.assertIn('"LOWERING_SECOND"', self.builder)
        self.assertNotIn('"hand_side": 0.86', self.builder)

    def test_acknowledgement_has_visible_torso_head_wave(self) -> None:
        self.assertIn('"torso_deg": 9.0', self.builder)
        self.assertIn('"chest_deg": 3.0', self.builder)
        self.assertIn('"head_deg": 5.0', self.builder)

    def test_reverence_has_cross_behind_and_turnout_targets(self) -> None:
        self.assertIn("ankle += side * hip_width * 1.75 * cross", self.builder)
        self.assertIn("ankle -= forward * total_leg * 0.065 * cross", self.builder)
        self.assertIn('"turnout_deg": 32.0', self.builder)
        self.assertIn("turnout @ foot_world_rotations[suffix]", self.builder)
        self.assertIn("side * side_sign * 0.42", self.builder)

    def test_preview_is_fast_visual_qa_not_final_render(self) -> None:
        self.assertIn(
            '("BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT")',
            self.builder,
        )
        self.assertIn("scene.render.resolution_x = 540", self.builder)
        self.assertIn("scene.render.resolution_y = 540", self.builder)

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
            '"RISE_AND_OPEN"', '"LOWERING_SECOND"', '"READY_RESOLUTION"',
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

    def test_blender_5_video_output_uses_media_type(self) -> None:
        self.assertIn("def configure_video_output(", self.builder)
        self.assertIn('image_settings.media_type = "VIDEO"', self.builder)
        self.assertIn('image_settings.file_format = "FFMPEG"', self.builder)
        self.assertIn('"video_output_api": video_output_api', self.builder)
        self.assertNotIn(
            'scene.render.image_settings.file_format = "FFMPEG"',
            self.builder,
        )

    def test_video_output_is_preflighted_before_glb_export(self) -> None:
        preflight = self.builder.index("configure_video_output(scene)")
        export = self.builder.index("export_glb(output_path)")
        self.assertLess(preflight, export)

    def test_preview_engine_is_runtime_compatible(self) -> None:
        self.assertIn("def choose_preview_engine(", self.builder)
        self.assertIn('"BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"', self.builder)
        self.assertIn('scene.render.bl_rna.properties["engine"]', self.builder)
        self.assertIn('"preview_engine": preview_engine', self.builder)
        self.assertNotIn('scene.render.engine = "BLENDER_EEVEE_NEXT"', self.builder)

    def test_preview_creates_world_when_factory_scene_has_none(self) -> None:
        self.assertIn("if scene.world is None:", self.builder)
        self.assertIn(
            'scene.world = bpy.data.worlds.new("P1043_PreviewWorld")',
            self.builder,
        )
        self.assertIn("scene.world.color = (0.035, 0.035, 0.035)", self.builder)

    def test_preview_is_rendered_automatically(self) -> None:
        self.assertIn("preview_engine = choose_preview_engine(scene)", self.builder)
        self.assertIn("video_output_api = configure_video_output(scene)", self.builder)
        self.assertIn('scene.render.ffmpeg.codec = "H264"', self.builder)
        self.assertIn('bpy.ops.render.render(animation=True)', self.builder)
        self.assertIn('PHASE 10.4.3 NATIVE IK PASS', self.wrapper)

    def test_godot_runtime_is_not_part_of_authoring_pipeline(self) -> None:
        self.assertNotIn('humanoid_motion_controller.gd', self.builder)
        self.assertNotIn('ballerina_visual_v_1.tscn', self.builder)
        self.assertNotIn('build/web', self.wrapper)


if __name__ == "__main__":
    unittest.main()
