import json
import pathlib
import unittest

from anatomical_constraints import (
    evaluate_dof,
    knee_external_rotation_cap_deg,
    validate_limit_table,
    validate_turnout_request,
)


ROOT = pathlib.Path(__file__).resolve().parents[2]
CANONICAL = ROOT / "assets" / "ballet_motion" / "canonical_ballet_skeleton_v1.json"
CONSTRAINTS = ROOT / "assets" / "ballet_motion" / "anatomical_constraints_v1.json"
BUILDER = ROOT / "tools" / "ballet_motion" / "build_anatomical_constraint_profile_v1.py"
WRAPPER = ROOT / "tools" / "ballet_motion" / "run_phase10_6_3_anatomical_constraints.ps1"


class Phase1063AnatomicalConstraintTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.canonical = json.loads(CANONICAL.read_text(encoding="utf-8"))
        cls.constraints = json.loads(CONSTRAINTS.read_text(encoding="utf-8"))
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_every_declared_rotational_dof_has_exactly_one_limit(self) -> None:
        self.assertEqual(
            validate_limit_table(self.canonical, self.constraints),
            [],
        )

    def test_preferred_ranges_are_inside_hard_ranges(self) -> None:
        for joint in self.constraints["joint_limits"].values():
            for limits in joint.get("dofs", {}).values():
                self.assertLessEqual(
                    limits["hard"]["min"],
                    limits["preferred"]["min"],
                )
                self.assertLessEqual(
                    limits["preferred"]["max"],
                    limits["hard"]["max"],
                )

    def test_constraint_evaluator_distinguishes_pass_soft_and_hard(self) -> None:
        self.assertEqual(
            evaluate_dof(
                self.constraints,
                "hip_ball",
                "internal_external_rotation",
                45.0,
            ).status,
            "PASS",
        )
        self.assertEqual(
            evaluate_dof(
                self.constraints,
                "hip_ball",
                "internal_external_rotation",
                70.0,
            ).status,
            "SOFT_LIMIT",
        )
        self.assertEqual(
            evaluate_dof(
                self.constraints,
                "hip_ball",
                "internal_external_rotation",
                90.0,
            ).status,
            "HARD_LIMIT",
        )

    def test_undeclared_joint_motion_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            evaluate_dof(
                self.constraints,
                "knee_hinge",
                "internal_external_rotation",
                5.0,
            )

    def test_turnout_hip_is_primary_authority(self) -> None:
        turnout = self.constraints["turnout_model"]
        self.assertEqual(
            turnout["primary_authority"],
            "hip_ball.internal_external_rotation",
        )
        self.assertFalse(
            turnout["knee_axial_coupling"]["independent_solver_dof"]
        )
        self.assertTrue(
            turnout["ankle_foot"][
                "turnout_generation_by_foot_yaw_forbidden"
            ]
        )

    def test_knee_axial_coupling_increases_with_flexion_but_is_capped(self) -> None:
        extension = knee_external_rotation_cap_deg(
            self.constraints, 0.0
        )
        mid = knee_external_rotation_cap_deg(
            self.constraints, 45.0
        )
        flexed = knee_external_rotation_cap_deg(
            self.constraints, 90.0
        )
        beyond = knee_external_rotation_cap_deg(
            self.constraints, 140.0
        )
        self.assertEqual(extension, 5.0)
        self.assertGreater(mid, extension)
        self.assertEqual(flexed, 18.0)
        self.assertEqual(beyond, flexed)

    def test_independent_foot_yaw_is_a_hard_failure(self) -> None:
        result = validate_turnout_request(
            self.constraints,
            hip_external_rotation_deg=35.0,
            knee_external_rotation_deg=4.0,
            knee_flexion_deg=10.0,
            independent_foot_yaw_deg=8.0,
        )
        self.assertEqual(result["status"], "HARD_LIMIT")
        self.assertIn(
            "independent_foot_yaw_forbidden",
            result["violations"],
        )

    def test_reasonable_turnout_chain_passes(self) -> None:
        result = validate_turnout_request(
            self.constraints,
            hip_external_rotation_deg=45.0,
            knee_external_rotation_deg=8.0,
            knee_flexion_deg=45.0,
            independent_foot_yaw_deg=0.0,
        )
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["violations"], [])

    def test_knee_and_wrist_continuity_contracts_exist(self) -> None:
        coupling = self.constraints["coupling_constraints"]
        self.assertTrue(coupling["knee_second_toe_tracking"]["enabled"])
        self.assertTrue(coupling["wrist_forearm_continuity"]["enabled"])
        self.assertTrue(
            coupling["wrist_forearm_continuity"][
                "independent_hand_axial_roll_forbidden"
            ]
        )

    def test_sources_document_general_and_ballet_specific_basis(self) -> None:
        source_ids = {
            item.get("pmid") or item.get("pmcid")
            for item in self.constraints["sources"]
        }
        self.assertIn("27015006", source_ids)
        self.assertIn("28880595", source_ids)
        self.assertIn("9262883", source_ids)
        self.assertIn("PMC6603670", source_ids)

    def test_builder_preserves_declared_body_front_contract(self) -> None:
        self.assertIn(
            '== "DECLARED_BY_RIG_CALIBRATION_ONLY"',
            self.builder,
        )
        self.assertNotIn("canonical_axes", self.builder)
        self.assertNotIn("average_toe", self.builder)

    def test_phase_is_pure_constraint_data_no_motion_runtime(self) -> None:
        self.assertNotIn("import bpy", self.builder)
        self.assertNotIn("Skeleton3D", self.builder)
        self.assertNotIn("AnimationTree", self.builder)
        self.assertNotIn("bpy.ops.", self.builder)
        self.assertIn(
            "No Blender runtime. No render. No pose. No animation.",
            self.wrapper,
        )

    def test_missing_10_6_2_profile_is_generated_automatically(self) -> None:
        self.assertIn(
            "run_phase10_6_2_canonical_skeleton.ps1",
            self.wrapper,
        )
        self.assertIn("generating prerequisite", self.wrapper)

    def test_windows_powershell_wrapper_is_ascii_only(self) -> None:
        self.assertTrue(
            all(ord(char) < 128 for char in self.wrapper),
            "Windows PowerShell 5.1 wrapper must remain ASCII-only.",
        )

    def test_output_contract_is_phase_10_6_3(self) -> None:
        self.assertIn('PHASE = "10.6.3"', self.builder)
        self.assertIn(
            "PHASE10_6_3_ANATOMICAL_CONSTRAINTS=PASS",
            self.builder,
        )
        self.assertIn(
            "low_poly_girl_anatomical_constraint_profile_v1.json",
            self.wrapper,
        )


if __name__ == "__main__":
    unittest.main()
