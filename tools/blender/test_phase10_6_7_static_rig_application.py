import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = (
    ROOT
    / "assets"
    / "ballet_motion"
    / "static_rig_application_contract_v1.json"
)
SCRIPT = ROOT / "tools" / "blender" / "apply_static_foundation_poses_v1.py"
WRAPPER = ROOT / "tools" / "blender" / "run_phase10_6_7_static_rig_application.ps1"


class Phase1067StaticRigApplicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_scope_is_static_application_not_animation_or_render(self) -> None:
        policy = self.contract["policy"]
        self.assertTrue(policy["visual_render_forbidden"])
        self.assertTrue(policy["animation_forbidden"])
        self.assertTrue(policy["glb_export_forbidden"])
        self.assertTrue(policy["source_glb_mutation_forbidden"])
        self.assertIn("Render: NO", self.wrapper)
        self.assertIn("Animation: NO", self.wrapper)
        self.assertIn("GLB export: NO", self.wrapper)

    def test_application_uses_pose_bone_matrix_basis_not_euler(self) -> None:
        self.assertTrue(
            self.contract["policy"]["apply_via_pose_bone_matrix_basis"]
        )
        self.assertTrue(
            self.contract["policy"]["euler_application_forbidden"]
        )
        self.assertIn("pose_bone.matrix_basis = matrix", self.script)
        self.assertNotIn("rotation_euler", self.script)

    def test_old_reverence_and_pose_lab_authoring_are_not_imported(self) -> None:
        self.assertNotIn("build_opening_reverence_v1", self.script)
        self.assertNotIn("build_ballet_pose_lab_v1", self.script)
        self.assertNotIn("setup_leg_controls", self.script)
        self.assertNotIn("apply_arm_landmark_pose", self.script)

    def test_no_ik_or_constraint_authoring(self) -> None:
        self.assertTrue(
            self.contract["policy"]["ik_constraints_forbidden"]
        )
        self.assertNotIn("constraints.new", self.script)
        self.assertNotIn("IK", self.script)

    def test_contact_proof_uses_real_deformed_mesh_vertices(self) -> None:
        self.assertEqual(
            self.contract["policy"]["contact_vertices_source"],
            "Foot/Toes vertex groups on deformed mesh",
        )
        for token in (
            "vertex.groups",
            "evaluated_depsgraph_get",
            "evaluated.to_mesh()",
            "mesh.vertices",
        ):
            self.assertIn(token, self.script)

    def test_contact_regions_are_rest_classified_rear_and_fore(self) -> None:
        sampling = self.contract["contact_sampling"]
        self.assertGreater(sampling["rear_fraction"], 0)
        self.assertGreater(sampling["fore_fraction"], 0)
        self.assertLess(
            sampling["rear_fraction"] + sampling["fore_fraction"],
            1.0,
        )
        self.assertIn('"rear":', self.script)
        self.assertIn('"fore":', self.script)

    def test_full_foot_contact_has_orientation_realization_before_root_shift(self) -> None:
        self.assertTrue(
            self.contract["policy"][
                "full_foot_orientation_correction_required"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "ankle_contact_correction_must_stay_preferred"
            ]
        )
        self.assertIn("def realize_full_foot_orientation(", self.script)
        self.assertIn(
            "def solve_preferred_ankle_flat_contact(",
            self.script,
        )
        self.assertIn("def ankle_delta_matrix(", self.script)
        self.assertIn(
            "def canonical_foot_basis_from_ankle_dofs(",
            self.script,
        )
        self.assertIn(
            'if mode == "SOLVE_FULL_FOOT_CONTACT":',
            self.script,
        )

    def test_full_foot_orientation_uses_declared_body_up_not_mesh_guess(self) -> None:
        self.assertIn(
            "solution = solve_preferred_ankle_flat_contact(",
            self.script,
        )
        self.assertIn("up_axis", self.script)
        self.assertIn(
            'canonical["body_frame"]["declared_axes_armature_local"]',
            self.script,
        )

    def test_full_foot_solver_searches_only_preferred_ankle_envelope(self) -> None:
        self.assertIn(
            'limits = constraints["joint_limits"]["ankle_2dof"]["dofs"]',
            self.script,
        )
        self.assertIn(
            'plantar_pref = limits["plantar_dorsiflexion"]["preferred"]',
            self.script,
        )
        self.assertIn(
            'inversion_pref = limits["inversion_eversion"]["preferred"]',
            self.script,
        )
        self.assertIn("for step in (0.1, 0.01, 0.001):", self.script)

    def test_full_foot_solver_aligns_foot_up_not_arbitrary_full_matrix(self) -> None:
        self.assertIn("up_alignment_dot", self.script)
        self.assertIn(
            'thresholds["full_foot_up_alignment_min_dot"]',
            self.script,
        )
        self.assertNotIn("decompose_ankle_2dof", self.script)
        self.assertNotIn(
            "ankle_dof_decomposition_matrix_error_max",
            self.script,
        )

    def test_contact_fix_does_not_relax_existing_contact_tolerance(self) -> None:
        self.assertEqual(
            self.contract["proof_thresholds"][
                "contact_error_max_foot_length_fraction"
            ],
            0.06,
        )

    def test_root_translation_modes_are_explicit(self) -> None:
        modes = self.contract["root_translation_modes"]
        self.assertEqual(modes["bras_bas"], "KEEP_REST")
        self.assertEqual(modes["en_avant"], "KEEP_REST")
        self.assertEqual(modes["second"], "KEEP_REST")
        self.assertEqual(modes["fifth"], "SOLVE_FULL_FOOT_CONTACT")
        self.assertEqual(modes["plie"], "SOLVE_FULL_FOOT_CONTACT")
        self.assertEqual(modes["releve"], "SOLVE_FOREFOOT_CONTACT")

    def test_root_translation_is_converted_from_armature_to_root_local(self) -> None:
        self.assertIn(
            "local_translation = rest_basis.transposed() @ desired_translation",
            self.script,
        )
        self.assertIn("basis.translation = local_translation", self.script)

    def test_every_pose_requires_exactly_24_rig_rotations(self) -> None:
        self.assertIn(
            'len(pose_entry["rig_pose"]) == 24',
            self.script,
        )
        self.assertIn(
            "expected 24 rig rotations",
            self.script,
        )

    def test_rotation_application_is_verified_both_local_and_absolute(self) -> None:
        self.assertIn("max_local_rotation_error", self.script)
        self.assertIn("max_absolute_rotation_error", self.script)
        self.assertIn("pose_bone.matrix_basis", self.script)
        self.assertIn("pose_bone.matrix", self.script)

    def test_plie_contact_solve_must_lower_root_and_match_descent(self) -> None:
        self.assertIn('if pose_name == "plie":', self.script)
        self.assertIn("actual_descent > 0.0", self.script)
        self.assertIn("target_pelvis_descent", self.script)
        self.assertIn("actual_contact_solved_descent", self.script)

    def test_releve_forefoot_contact_and_heel_lift_are_both_proved(self) -> None:
        self.assertIn('if pose_name == "releve":', self.script)
        self.assertIn("heel_lifts", self.script)
        self.assertIn("releve_heel_must_rise_min_foot_fraction", self.script)
        self.assertEqual(
            self.contract["root_translation_modes"]["releve"],
            "SOLVE_FOREFOOT_CONTACT",
        )

    def test_source_glb_sha_is_reverified_before_application(self) -> None:
        self.assertIn("sha256_file(source_glb)", self.script)
        self.assertIn(
            'canonical["source"]["sha256"]',
            self.script,
        )

    def test_imported_animation_is_cleared(self) -> None:
        self.assertTrue(
            self.contract["policy"]["animation_data_must_be_cleared"]
        )
        self.assertIn("armature.animation_data_clear()", self.script)
        self.assertIn("obj.animation_data_clear()", self.script)

    def test_wrapper_passes_constraints_and_retarget_axis_contract(self) -> None:
        self.assertIn("$constraints =", self.wrapper)
        self.assertIn("$retargetAxisContract =", self.wrapper)
        self.assertIn("--constraint-profile $constraints", self.wrapper)
        self.assertIn(
            "--retarget-axis-contract $retargetAxisContract",
            self.wrapper,
        )

    def test_wrapper_auto_generates_10_6_6_prerequisite(self) -> None:
        self.assertIn(
            "run_phase10_6_6_calibrated_rig_retarget.ps1",
            self.wrapper,
        )
        self.assertIn("generating prerequisite", self.wrapper)

    def test_windows_powershell_wrapper_is_ascii_only(self) -> None:
        self.assertTrue(
            all(ord(char) < 128 for char in self.wrapper),
            "Windows PowerShell 5.1 wrapper must remain ASCII-only.",
        )

    def test_script_has_no_render_or_export_operator(self) -> None:
        self.assertNotIn("bpy.ops.render", self.script)
        self.assertNotIn("export_scene.gltf", self.script)
        self.assertNotIn("wm.save_as_mainfile", self.script)

    def test_output_contract_is_phase_10_6_7(self) -> None:
        self.assertIn('PHASE = "10.6.7"', self.script)
        self.assertIn(
            "PHASE10_6_7_STATIC_RIG_APPLICATION=PASS",
            self.script,
        )
        self.assertIn(
            "static_rig_application_report_v1.json",
            self.wrapper,
        )


if __name__ == "__main__":
    unittest.main()
