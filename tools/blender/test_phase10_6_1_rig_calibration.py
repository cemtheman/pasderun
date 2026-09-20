import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
SEED = (
    ROOT
    / "assets"
    / "characters"
    / "low_poly_girl"
    / "ballet_rig_calibration_seed_v1.json"
)
SCRIPT = ROOT / "tools" / "blender" / "build_ballet_rig_calibration_v1.py"
WRAPPER = ROOT / "tools" / "blender" / "run_ballet_rig_calibration_v1.ps1"


class Phase1061RigCalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.seed = json.loads(SEED.read_text(encoding="utf-8"))
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_anatomical_frame_is_explicit_not_inferred(self) -> None:
        frame = self.seed["declared_anatomical_frame"]
        self.assertEqual(frame["up"], [0, 0, 1])
        self.assertEqual(frame["left"], [1, 0, 0])
        self.assertEqual(frame["front"], [0, -1, 0])
        self.assertIn('"body_front_is_declared": True', self.script)
        self.assertIn('"body_front_is_inferred_from_toes": False', self.script)
        self.assertNotIn("def canonical_axes(", self.script)

    def test_toes_are_validation_evidence_only(self) -> None:
        self.assertIn("average_toe_front_alignment", self.script)
        self.assertIn(
            "Toe and shoulder geometry are validation evidence only",
            SEED.read_text(encoding="utf-8"),
        )
        self.assertNotIn("front = average_toe", self.script)
        self.assertNotIn("front = toe", self.script)

    def test_profile_is_rest_pose_and_source_hash_bound(self) -> None:
        self.assertIn("armature.animation_data_clear()", self.script)
        self.assertIn("armature.data.bones", self.script)
        self.assertIn("sha256_file(source_glb)", self.script)
        self.assertIn('"sha256": sha256_file(source_glb)', self.script)

    def test_canonical_skeleton_mapping_is_complete(self) -> None:
        bones = self.seed["canonical_bones"]
        for name in (
            "pelvis", "chest", "head",
            "left_clavicle", "right_clavicle",
            "left_upper_arm", "right_upper_arm",
            "left_forearm", "right_forearm",
            "left_hand", "right_hand",
            "left_thigh", "right_thigh",
            "left_shin", "right_shin",
            "left_foot", "right_foot",
            "left_toes", "right_toes",
        ):
            self.assertIn(name, bones)
        self.assertGreaterEqual(len(bones), 24)

    def test_every_bone_records_exact_rest_transform_and_axis_projection(self) -> None:
        self.assertIn('"matrix_local": matrix4(bone.matrix_local)', self.script)
        self.assertIn('"rest_axes": {', self.script)
        self.assertIn('"body_frame_projection": {', self.script)
        self.assertIn('"basis_determinant"', self.script)

    def test_semantic_hand_and_foot_directions_are_profiled(self) -> None:
        segments = self.seed["semantic_segments"]
        self.assertEqual(
            segments["left_hand_tangent"],
            ["Hand_L", "Middle_L"],
        )
        self.assertEqual(
            segments["right_foot_forward"],
            ["Foot_R", "Toes_R"],
        )
        self.assertIn("semantic_segment_profile(", self.script)

    def test_declared_frame_is_validated_against_rest_geometry(self) -> None:
        for token in (
            "shoulder_side_alignment",
            "hip_side_alignment",
            "torso_up_alignment",
            "average_toe_front_alignment",
            "LEFT x UP = FRONT",
        ):
            self.assertIn(token, self.script)

    def test_calibration_has_no_render_animation_or_export_scope(self) -> None:
        self.assertNotIn("bpy.ops.render", self.script)
        self.assertNotIn("bpy.ops.nla.bake", self.script)
        self.assertNotIn("export_glb", self.script)
        self.assertNotIn("AnimationTree", self.script)
        self.assertIn("No render. No animation. No GLB export.", self.wrapper)

    def test_output_contract_is_phase_10_6_1(self) -> None:
        self.assertIn('PHASE = "10.6.1"', self.script)
        self.assertIn("PHASE10_6_1_RIG_CALIBRATION=PASS", self.script)
        self.assertIn(
            "low_poly_girl_ballet_rig_profile_v1.json",
            self.wrapper,
        )

    def test_godot_runtime_is_untouched(self) -> None:
        self.assertNotIn("humanoid_motion_controller.gd", self.script)
        self.assertNotIn("ballerina_visual_v_1.tscn", self.script)
        self.assertNotIn("build/web", self.wrapper)


if __name__ == "__main__":
    unittest.main()
