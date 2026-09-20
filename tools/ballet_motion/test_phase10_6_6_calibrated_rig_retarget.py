import json
import pathlib
import unittest

from canonical_math import (
    determinant,
    mat_mul,
    matrix_from_columns,
    normalize,
    orthogonality_error,
    transpose,
)
from calibrated_rig_retarget import (
    _rig_pose_from_canonical,
    _upper_limb_target_bases,
)
from rig_retarget_math import (
    axis_rotation,
    basis_from_length_and_front,
    identity3,
    local_twist_y,
    matrix_max_error,
)


ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = ROOT / "assets" / "ballet_motion" / "retarget_axis_contract_v1.json"
RETARGET = ROOT / "tools" / "ballet_motion" / "calibrated_rig_retarget.py"
BUILDER = ROOT / "tools" / "ballet_motion" / "build_calibrated_rig_retarget_v1.py"
WRAPPER = ROOT / "tools" / "ballet_motion" / "run_phase10_6_6_calibrated_rig_retarget.ps1"


class Phase1066CalibratedRigRetargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.retarget = RETARGET.read_text(encoding="utf-8")
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_scope_is_orientation_only_and_no_blender_application(self) -> None:
        policy = self.contract["policy"]
        self.assertTrue(policy["orientation_retarget_only"])
        self.assertFalse(policy["root_translation_applied"])
        self.assertFalse(policy["contact_translation_applied"])
        self.assertTrue(policy["blender_application_forbidden"])
        self.assertTrue(policy["render_forbidden"])
        self.assertTrue(policy["animation_forbidden"])

    def test_no_euler_application_contract(self) -> None:
        self.assertTrue(self.contract["policy"]["euler_application_forbidden"])
        self.assertTrue(
            self.contract["policy"]["matrix_and_quaternion_output_only"]
        )
        self.assertNotIn("Euler", self.retarget)
        self.assertNotIn("rotation_euler", self.retarget)

    def test_lower_body_axis_contract_is_explicit(self) -> None:
        axes = self.contract["lower_body_joint_axes"]
        self.assertEqual(
            set(axes),
            {"hip_ball", "knee_hinge", "ankle_2dof", "mtp_hinge"},
        )
        hip = {item.get("dof"): item for item in axes["hip_ball"]}
        self.assertEqual(hip["flexion_extension"]["axis"], "X")
        self.assertEqual(hip["abduction_adduction"]["axis"], "Z")
        self.assertTrue(hip["abduction_adduction"]["side_sign"])
        self.assertEqual(
            hip["internal_external_rotation"]["axis"],
            "Y",
        )
        self.assertTrue(
            hip["internal_external_rotation"]["side_sign"]
        )

    def test_knee_axial_turnout_is_derived_not_authored_dof(self) -> None:
        knee = self.contract["lower_body_joint_axes"]["knee_hinge"]
        derived = [item for item in knee if "derived" in item]
        self.assertEqual(len(derived), 1)
        self.assertEqual(
            derived[0]["derived"],
            "knee_external_rotation_deg",
        )
        self.assertTrue(derived[0]["side_sign"])

    def test_axis_rotation_is_proper_rotation(self) -> None:
        for axis in ("X", "Y", "Z"):
            matrix = axis_rotation(axis, 37.0)
            self.assertLess(orthogonality_error(matrix), 1e-12)
            self.assertAlmostEqual(determinant(matrix), 1.0, places=12)

    def test_roll_stable_segment_basis_uses_length_as_local_y(self) -> None:
        direction = normalize([0.3, -0.4, 0.8])
        basis = basis_from_length_and_front(
            direction,
            [0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0],
            [1.0, 0.0, 0.0],
        )
        y_axis = [basis[row][1] for row in range(3)]
        for actual, expected in zip(y_axis, direction):
            self.assertAlmostEqual(actual, expected, places=12)
        self.assertLess(orthogonality_error(basis), 1e-12)
        self.assertAlmostEqual(determinant(basis), 1.0, places=12)

    def test_axial_twist_preserves_length_axis(self) -> None:
        basis = identity3()
        twisted = local_twist_y(basis, 42.0)
        before = [basis[row][1] for row in range(3)]
        after = [twisted[row][1] for row in range(3)]
        self.assertEqual(before, after)

    def test_bind_mapping_has_exact_rest_identity_and_roundtrip(self) -> None:
        canonical_rest = axis_rotation("Z", 23.0)
        rig_rest = axis_rotation("X", -31.0)
        bind = mat_mul(rig_rest, transpose(canonical_rest))
        mapped_rest = mat_mul(bind, canonical_rest)
        self.assertLess(matrix_max_error(mapped_rest, rig_rest), 1e-12)

        canonical_pose = mat_mul(canonical_rest, axis_rotation("Y", 17.0))
        rig_pose = mat_mul(bind, canonical_pose)
        roundtrip = mat_mul(transpose(bind), rig_pose)
        self.assertLess(matrix_max_error(roundtrip, canonical_pose), 1e-12)

    def test_parent_relative_rig_delta_reconstructs_absolute_basis(self) -> None:
        parent_rest = axis_rotation("Z", 10.0)
        child_rest = mat_mul(parent_rest, axis_rotation("X", 20.0))
        parent_pose = mat_mul(parent_rest, axis_rotation("Y", 15.0))
        child_pose = mat_mul(
            parent_pose,
            mat_mul(axis_rotation("X", 20.0), axis_rotation("Z", -12.0)),
        )

        rest_local = mat_mul(transpose(parent_rest), child_rest)
        desired_local = mat_mul(transpose(parent_pose), child_pose)
        delta = mat_mul(transpose(rest_local), desired_local)
        reconstructed = mat_mul(
            mat_mul(parent_pose, rest_local),
            delta,
        )
        self.assertLess(matrix_max_error(reconstructed, child_pose), 1e-12)

    def test_upper_limb_contract_uses_landmark_frames_and_axial_roll_only(self) -> None:
        upper = self.contract["upper_limb_roll"]
        self.assertEqual(
            upper["upper_arm"]["source_dof"],
            "internal_external_rotation",
        )
        self.assertEqual(
            upper["forearm"]["source_dof"],
            "pronation_supination",
        )
        self.assertIsNone(upper["hand"]["source_dof"])
        self.assertIn("basis_from_length_and_front(", self.retarget)
        self.assertIn("local_twist_y(", self.retarget)

    def test_retarget_outputs_parent_relative_matrix_and_quaternion(self) -> None:
        self.assertIn('"local_pose_delta_matrix"', self.retarget)
        self.assertIn(
            '"local_pose_delta_quaternion_wxyz"',
            self.retarget,
        )
        self.assertIn("canonical_roundtrip_error", self.retarget)
        self.assertIn("hierarchy_reconstruction_error", self.retarget)

    def test_non_rotational_pose_contract_is_preserved_not_applied(self) -> None:
        for key in (
            "contacts",
            "turnout",
            "knee_second_toe_error_deg",
            "scalars",
            "com",
            "support_polygon",
        ):
            self.assertIn(f'"{key}"', self.retarget)
        self.assertIn('"root_translation_applied": False', self.retarget)
        self.assertIn('"contact_translation_applied": False', self.retarget)

    def test_builder_requires_validated_10_6_5_and_source_sha_binding(self) -> None:
        self.assertIn('poses["phase"] == "10.6.5"', self.builder)
        self.assertIn(
            'poses["foundation_gate"]["all_pose_geometry_pass"]',
            self.builder,
        )
        self.assertIn(
            'poses["inputs"]["source_glb_sha256"]',
            self.builder,
        )
        self.assertIn('canonical["source"]["sha256"]', self.builder)

    def test_builder_retargets_six_poses_and_twenty_four_bones(self) -> None:
        self.assertIn(
            '{"bras_bas", "en_avant", "second", "fifth", "plie", "releve"}',
            self.builder,
        )
        self.assertIn(
            'item["evidence"]["bone_count"] == 24',
            self.builder,
        )
        self.assertIn("POSES=6/6", self.builder)
        self.assertIn("BONES_PER_POSE=24", self.builder)

    def test_wrapper_auto_generates_10_6_5_prerequisite(self) -> None:
        self.assertIn(
            "run_phase10_6_5_canonical_pose_solver.ps1",
            self.wrapper,
        )
        self.assertIn("generating prerequisite", self.wrapper)

    def test_wrapper_is_ascii_safe_for_windows_powershell(self) -> None:
        self.assertTrue(all(ord(char) < 128 for char in self.wrapper))

    def test_output_contract_is_phase_10_6_6(self) -> None:
        self.assertIn('PHASE = "10.6.6"', self.builder)
        self.assertIn(
            "PHASE10_6_6_CALIBRATED_RIG_RETARGET=PASS",
            self.builder,
        )
        self.assertIn(
            "low_poly_girl_calibrated_rig_retarget_v1.json",
            self.wrapper,
        )


if __name__ == "__main__":
    unittest.main()
