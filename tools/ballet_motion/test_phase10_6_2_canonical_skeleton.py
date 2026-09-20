import json
import pathlib
import unittest

from canonical_math import (
    determinant,
    mat_mul,
    matrix_from_columns,
    orthogonality_error,
    rotation_matrix_to_quaternion_wxyz,
    transpose,
)


ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC = ROOT / "assets" / "ballet_motion" / "canonical_ballet_skeleton_v1.json"
BUILDER = ROOT / "tools" / "ballet_motion" / "build_canonical_ballet_profile_v1.py"
WRAPPER = ROOT / "tools" / "ballet_motion" / "run_phase10_6_2_canonical_skeleton.ps1"


class Phase1062CanonicalSkeletonTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spec = json.loads(SPEC.read_text(encoding="utf-8"))
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_exactly_24_canonical_bones_form_a_rooted_graph(self) -> None:
        bones = self.spec["bones"]
        self.assertEqual(len(bones), 24)
        self.assertIsNone(bones["pelvis"]["parent"])
        for name, bone in bones.items():
            parent = bone["parent"]
            if parent is not None:
                self.assertIn(parent, bones, name)

    def test_joint_classes_encode_anatomical_dofs_not_euler_targets(self) -> None:
        classes = self.spec["joint_classes"]
        self.assertEqual(
            classes["shoulder_ball"]["rotational_dofs"],
            [
                "flexion_extension",
                "abduction_adduction",
                "internal_external_rotation",
            ],
        )
        self.assertEqual(
            classes["knee_hinge"]["rotational_dofs"],
            ["flexion_extension"],
        )
        self.assertIn("pronation_supination", classes["elbow_twist"]["rotational_dofs"])
        self.assertEqual(
            self.spec["solver_policy"]["numeric_joint_limits_stage"],
            "10.6.3",
        )

    def test_canonical_basis_rule_is_explicit_and_right_handed(self) -> None:
        convention = self.spec["coordinate_convention"]
        self.assertEqual(convention["bone_length_axis"], "LOCAL_Y")
        self.assertEqual(convention["handedness"], "RIGHT_HANDED")
        self.assertIn("X=Y cross Z", convention["canonical_basis_rule"])
        self.assertIn("determinant(basis) > 0.999999", self.builder)

    def test_front_can_only_come_from_calibration_profile(self) -> None:
        self.assertEqual(
            self.spec["coordinate_convention"]["body_front_policy"],
            "DECLARED_BY_RIG_CALIBRATION_ONLY",
        )
        self.assertIn(
            'front_policy": "DECLARED_BY_RIG_CALIBRATION_ONLY"',
            self.builder,
        )
        self.assertNotIn("average_toe", self.builder)
        self.assertNotIn("canonical_axes", self.builder)

    def test_bind_rotation_maps_canonical_basis_to_rig_basis(self) -> None:
        canonical = matrix_from_columns(
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        rig = matrix_from_columns(
            [0.0, 1.0, 0.0],
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
        )
        bind = mat_mul(rig, transpose(canonical))
        self.assertLess(orthogonality_error(bind), 1e-9)
        self.assertAlmostEqual(determinant(bind), 1.0, places=9)
        self.assertEqual(len(rotation_matrix_to_quaternion_wxyz(bind)), 4)

    def test_every_output_bone_has_exact_retarget_bind_contract(self) -> None:
        for token in (
            '"head_body": body_coordinates(',
            '"tail_body": body_coordinates(',
            '"canonical_to_rig_rotation_matrix"',
            '"canonical_to_rig_quaternion_wxyz"',
            '"rig_to_canonical_rotation_matrix"',
            '"determinant": round(bind_det',
        ):
            self.assertIn(token, self.builder)

    def test_rig_rest_basis_is_validated_before_bind_rotation(self) -> None:
        self.assertIn(
            "rig rest basis orthogonality error",
            self.builder,
        )
        rig_check = self.builder.index(
            "rig rest basis orthogonality error"
        )
        bind_build = self.builder.index(
            "canonical_to_rig = mat_mul(rig, transpose(canonical))"
        )
        self.assertLess(rig_check, bind_build)

    def test_source_glb_sha_must_match_calibration(self) -> None:
        self.assertIn("actual_sha = sha256_file(source_path)", self.builder)
        self.assertIn(
            'actual_sha == calibration["source"]["sha256"]',
            self.builder,
        )
        self.assertIn("Calibration profile is stale", self.builder)

    def test_validator_foundation_reserves_ballet_pose_invariants(self) -> None:
        reserved = self.spec["validator_foundation"]["pose_validators_reserved"]
        for validator in (
            "anterior_halfspace",
            "bilateral_mirror",
            "joint_limit",
            "knee_second_toe_tracking",
            "support_polygon_com",
            "contact",
            "palm_orientation_continuity",
        ):
            self.assertIn(validator, reserved)

    def test_phase_has_no_blender_godot_pose_or_animation_scope(self) -> None:
        self.assertNotIn("import bpy", self.builder)
        self.assertNotIn("bpy.ops.", self.builder)
        self.assertNotIn("AnimationTree", self.builder)
        self.assertNotIn("Skeleton3D", self.builder)
        self.assertNotIn("humanoid_motion_controller.gd", self.builder)
        self.assertNotIn("bpy.ops.render", self.builder)
        self.assertIn(
            "No Blender runtime. No render. No pose. No animation.",
            self.wrapper,
        )

    def test_windows_powershell_wrapper_is_ascii_only(self) -> None:
        self.assertTrue(
            all(ord(char) < 128 for char in self.wrapper),
            "Windows PowerShell 5.1 wrapper must remain ASCII-only.",
        )

    def test_output_contract_is_phase_10_6_2(self) -> None:
        self.assertIn('PHASE = "10.6.2"', self.builder)
        self.assertIn("PHASE10_6_2_CANONICAL_SKELETON=PASS", self.builder)
        self.assertIn(
            "low_poly_girl_canonical_ballet_profile_v1.json",
            self.wrapper,
        )


if __name__ == "__main__":
    unittest.main()
