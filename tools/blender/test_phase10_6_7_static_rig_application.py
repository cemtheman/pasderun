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

    def test_semantic_limb_mapping_preserves_length_axis_in_blender(self) -> None:
        self.assertIn(
            "SEMANTIC_LENGTH_AXIS_JOINT_CLASSES",
            self.script,
        )
        self.assertIn(
            "def semantic_roll_offset_y(",
            self.script,
        )
        self.assertIn(
            "def rig_basis_from_canonical_pose(",
            self.script,
        )
        self.assertIn(
            "@ rotation_y(semantic_roll_offset_y(canonical_bone))",
            self.script,
        )
        self.assertIn(
            "@ rotation_y(-semantic_roll_offset_y(canonical_bone))",
            self.script,
        )

    def test_contact_orientation_does_not_reintroduce_full_bind_swing(self) -> None:
        full_foot_start = self.script.index(
            "def solve_preferred_ankle_flat_contact("
        )
        full_foot_end = self.script.index(
            "def realize_full_foot_orientation(",
            full_foot_start,
        )
        full_foot_source = self.script[
            full_foot_start:full_foot_end
        ]
        self.assertEqual(
            full_foot_source.count(
                "desired_rig = rig_basis_from_canonical_pose("
            ),
            2,
        )
        self.assertNotIn(
            "desired_rig = bind @ desired_canonical",
            full_foot_source,
        )

        releve_start = self.script.index(
            "def apply_releve_plantar_toe_candidate("
        )
        releve_end = self.script.index(
            "def candidate_releve_geometry(",
            releve_start,
        )
        releve_source = self.script[releve_start:releve_end]
        self.assertEqual(
            releve_source.count("rig_basis_from_canonical_pose("),
            2,
        )
        self.assertIn(
            "desired_foot_rig = rig_basis_from_canonical_pose(",
            releve_source,
        )
        self.assertIn(
            "desired_toe_rig = rig_basis_from_canonical_pose(",
            releve_source,
        )
        self.assertNotIn(
            "bind @ desired",
            releve_source,
        )

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

    def test_full_foot_orientation_uses_mesh_contact_with_declared_up(self) -> None:
        self.assertTrue(
            self.contract["policy"][
                "full_foot_mesh_contact_plane_is_final_authority"
            ]
        )
        self.assertIn(
            "solution = solve_preferred_ankle_flat_contact(",
            self.script,
        )
        self.assertIn(
            "mesh_flatness_error",
            self.script,
        )
        self.assertIn(
            "required_shifts",
            self.script,
        )
        self.assertIn(
            "anchor_height(",
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

    def test_old_ideal_basis_flatten_helper_is_removed(self) -> None:
        self.assertNotIn(
            "def flatten_canonical_foot_basis(",
            self.script,
        )

    def test_full_foot_solver_keeps_anatomical_seed_but_mesh_is_final_authority(self) -> None:
        self.assertEqual(
            self.contract["proof_thresholds"][
                "full_foot_seed_up_alignment_min_dot"
            ],
            0.999999,
        )
        self.assertTrue(
            self.contract["policy"][
                "full_foot_realized_bone_up_alignment_is_not_contact_authority"
            ]
        )
        self.assertNotIn(
            "full_foot_up_alignment_min_dot",
            self.contract["proof_thresholds"],
        )
        self.assertIn("minimum_seed_up_alignment_dot", self.script)
        self.assertNotIn("minimum_realized_up_alignment_dot", self.script)
        self.assertIn("canonical_seed", self.script)
        self.assertIn("mesh_flatness_error", self.script)
        self.assertNotIn("decompose_ankle_2dof", self.script)
        self.assertNotIn(
            "ankle_dof_decomposition_matrix_error_max",
            self.script,
        )

    def test_full_foot_mesh_search_is_preferred_only_and_refined(self) -> None:
        thresholds = self.contract["proof_thresholds"]
        self.assertEqual(
            thresholds["full_foot_mesh_search_coarse_step_deg"],
            1,
        )
        self.assertEqual(
            thresholds["full_foot_mesh_search_refine_steps_deg"],
            [0.1, 0.01, 0.001],
        )
        self.assertIn("coarse_step_deg", self.script)
        self.assertIn("refine_steps_deg", self.script)

    def test_bras_bas_and_en_avant_record_middle_bone_tail_diagnostic(self) -> None:
        self.assertIn(
            "def realized_middle_fingertip_spacing(",
            self.script,
        )
        self.assertIn(
            'canonical["canonical_bones"]["left_middle"]["rig_bone"]',
            self.script,
        )
        self.assertIn(
            'canonical["canonical_bones"]["right_middle"]["rig_bone"]',
            self.script,
        )
        self.assertIn(
            "armature.pose.bones[left_name].tail",
            self.script,
        )
        self.assertIn(
            "armature.pose.bones[right_name].tail",
            self.script,
        )
        self.assertIn(
            'pose_name in ("bras_bas", "en_avant")',
            self.script,
        )
        self.assertIn(
            '"middle_bone_tip_diagnostic_recorded": True',
            self.script,
        )

    def test_hand_mesh_is_final_centerline_authority(self) -> None:
        self.assertTrue(
            self.contract["policy"][
                "hand_mesh_centerline_spacing_required_for_bras_bas_and_en_avant"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "hand_mesh_is_final_visual_centerline_authority"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "middle_bone_tail_is_diagnostic_not_visual_authority"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "partial_hand_or_single_finger_sampling_forbidden"
            ]
        )
        self.assertEqual(
            self.contract["hand_mesh_sampling"]["bone_scope"],
            "HAND_ROOT_PLUS_ALL_DESCENDANTS",
        )
        self.assertEqual(
            self.contract["hand_mesh_sampling"]["inner_edge_quantile"],
            0.0,
        )
        self.assertEqual(
            self.contract["hand_mesh_sampling"]["inner_edge_measurement"],
            "STRICT_EXTREME_VERTEX",
        )
        self.assertTrue(
            self.contract["policy"][
                "hand_mesh_centerline_strict_no_cross_required"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "hand_mesh_centerline_outlier_tolerance_forbidden"
            ]
        )
        self.assertIn(
            "def rig_bone_subtree_names(",
            self.script,
        )
        self.assertIn(
            "def hand_rig_vertex_groups(",
            self.script,
        )
        self.assertIn(
            "stack.extend(list(bone.children))",
            self.script,
        )
        self.assertNotIn(
            'canonical["canonical_bones"]["left_middle"]["rig_bone"],\n'
            '        },\n'
            '        "right": {',
            self.script,
        )
        self.assertIn(
            "def realized_hand_mesh_centerline_spacing(",
            self.script,
        )
        self.assertIn(
            '"authority": "DEFORMED_HAND_MESH"',
            self.script,
        )
        self.assertTrue(
            self.contract["policy"][
                "hand_mesh_runtime_clearance_solver_required"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "hand_mesh_runtime_clearance_not_authored"
            ]
        )
        runtime_solver = self.contract[
            "hand_mesh_runtime_clearance_solver"
        ]
        self.assertEqual(
            runtime_solver["method"],
            "INDEPENDENT_PRIMARY_SHOULDER_SWEEP_BISECTION",
        )
        self.assertEqual(
            runtime_solver["shoulder_axis_by_pose"]["bras_bas"],
            "BODY_FRONT",
        )
        self.assertEqual(
            runtime_solver["shoulder_axis_by_pose"]["en_avant"],
            "BODY_UP",
        )
        self.assertTrue(
            self.contract["policy"][
                "hand_mesh_elbow_local_bend_preserved"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "hand_mesh_wrist_local_bend_preserved"
            ]
        )
        self.assertEqual(
            self.contract["policy"]["hand_mesh_primary_joint_authority"],
            "SHOULDER_SWEEP_ONLY",
        )
        self.assertIn(
            "def apply_single_shoulder_sweep(",
            self.script,
        )
        self.assertIn(
            "def shoulder_sweep_limit_deg(",
            self.script,
        )
        self.assertIn(
            "Matrix.Rotation(",
            self.script,
        )
        self.assertNotIn(
            "solved_clearance_fraction_by_side",
            self.script,
        )
        self.assertIn(
            '"hand_mesh_centerline_spacing_pass": True',
            self.script,
        )
        self.assertIn(
            '"hand_mesh_retarget_wrist_seed_preserved_pass": True',
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
        self.assertTrue(
            self.contract["policy"][
                "standing_arm_poses_full_foot_contact_required"
            ]
        )
        self.assertEqual(
            modes["bras_bas"],
            "SOLVE_FULL_FOOT_CONTACT",
        )
        self.assertEqual(
            modes["en_avant"],
            "SOLVE_FULL_FOOT_CONTACT",
        )
        self.assertEqual(
            modes["second"],
            "SOLVE_FULL_FOOT_CONTACT",
        )
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
        self.assertEqual(
            self.contract["policy"]["plie_pelvis_descent_source"],
            "Phase 10.6.5 leg-chain-scaled semantic scalar",
        )
        self.assertTrue(
            self.contract["policy"][
                "plie_full_foot_contact_is_final_root_translation_authority"
            ]
        )
        self.assertIn('if pose_name == "plie":', self.script)
        self.assertIn("actual_descent > 0.0", self.script)
        self.assertIn("target_pelvis_descent", self.script)
        self.assertIn("actual_contact_solved_descent", self.script)

    def test_releve_realizes_semantic_heel_height_by_solving_plantar_and_toe(self) -> None:
        self.assertTrue(
            self.contract["policy"][
                "releve_contact_realization_required"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "releve_plantar_solver_preferred_only"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "releve_toe_solver_preferred_only"
            ]
        )
        self.assertFalse(
            self.contract["policy"][
                "releve_toe_flexion_preserved_from_retarget"
            ]
        )
        self.assertIn(
            "def solve_releve_plantar_toe_for_mesh_heel_height(",
            self.script,
        )
        self.assertIn(
            '["plantar_dorsiflexion"]["preferred"]',
            self.script,
        )
        self.assertIn(
            'constraints["joint_limits"]["mtp_hinge"]["dofs"]',
            self.script,
        )
        self.assertIn(
            '"toe_flexion_extension"',
            self.script,
        )
        self.assertIn(
            'toe_preferred',
            self.script,
        )
        self.assertIn(
            "apply_releve_plantar_toe_candidate(",
            self.script,
        )
        self.assertIn(
            "candidate_releve_geometry(",
            self.script,
        )
        self.assertIn(
            "releve_plantar_toe_contact_realization_pass",
            self.script,
        )

    def test_releve_joint_search_stays_inside_preferred_envelopes(self) -> None:
        self.assertIn("plantar_min <= plantar <= plantar_max", self.script)
        self.assertIn("toe_min <= toe_flexion <= toe_max", self.script)
        self.assertIn("semantic_deviation", self.script)
        self.assertTrue(
            self.contract["policy"][
                "releve_semantic_joint_targets_are_preferences_after_contact"
            ]
        )

    def test_releve_joint_search_is_bounded_and_refined(self) -> None:
        thresholds = self.contract["proof_thresholds"]
        self.assertEqual(
            thresholds["releve_plantar_search_coarse_step_deg"],
            2,
        )
        self.assertEqual(
            thresholds["releve_toe_search_coarse_step_deg"],
            5,
        )
        self.assertEqual(
            thresholds["releve_joint_search_refine_steps_deg"],
            [1, 0.2, 0.05],
        )

    def test_releve_target_tolerance_is_not_relaxed(self) -> None:
        self.assertEqual(
            self.contract["proof_thresholds"][
                "releve_heel_lift_relative_error_max"
            ],
            0.45,
        )
        self.assertEqual(
            self.contract["proof_thresholds"][
                "releve_heel_lift_absolute_foot_fraction_max"
            ],
            0.2,
        )

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
        self.assertIn(
            "--grammar-profile $grammarProfile",
            self.wrapper,
        )
        self.assertIn(
            "--intent-spec $intents",
            self.wrapper,
        )
        self.assertIn(
            "$data.gate.hand_mesh_runtime_clearance_solver_pass",
            self.wrapper,
        )

    def test_wrapper_refreshes_stale_pose_or_10_6_6_profile(self) -> None:
        self.assertIn("Get-FileHash -Algorithm SHA256", self.wrapper)
        self.assertIn(
            "existingPose.inputs.intent_spec_sha256",
            self.wrapper,
        )
        self.assertIn(
            "existingPose.inputs.solver_source_sha256",
            self.wrapper,
        )
        self.assertIn(
            "existingRetarget.inputs.pose_profile_sha256",
            self.wrapper,
        )
        self.assertIn(
            "existingRetarget.inputs.retarget_source_sha256",
            self.wrapper,
        )
        self.assertIn(
            "existingRetarget.inputs.axis_contract_sha256",
            self.wrapper,
        )
        self.assertIn(
            "pose profile is stale; intent spec changed",
            self.wrapper,
        )
        self.assertIn(
            "pose profile is stale; solver source changed",
            self.wrapper,
        )
        self.assertIn(
            "retarget profile is stale; pose profile changed",
            self.wrapper,
        )
        self.assertIn(
            "retarget profile is stale; retarget source changed",
            self.wrapper,
        )
        self.assertIn(
            "retarget profile is stale; axis contract changed",
            self.wrapper,
        )

    def test_wrapper_auto_generates_10_6_6_prerequisite(self) -> None:
        self.assertIn(
            "run_phase10_6_6_calibrated_rig_retarget.ps1",
            self.wrapper,
        )
        self.assertIn("retarget prerequisite", self.wrapper)

    def test_wrapper_requires_releve_joint_realization_gates(self) -> None:
        self.assertIn(
            "$data.gate.releve_plantar_contact_realization_pass",
            self.wrapper,
        )
        self.assertIn(
            "Releve plantar/contact realization gate failed.",
            self.wrapper,
        )
        self.assertIn(
            "$data.gate.releve_plantar_toe_contact_realization_pass",
            self.wrapper,
        )
        self.assertIn(
            "Releve plantar+toe/contact realization gate failed.",
            self.wrapper,
        )

    def test_wrapper_requires_hand_mesh_spacing_and_wrist_seed_gates(self) -> None:
        self.assertIn(
            "$data.gate.hand_mesh_centerline_spacing_pass",
            self.wrapper,
        )
        self.assertIn(
            "$data.gate.hand_mesh_retarget_wrist_seed_preserved_pass",
            self.wrapper,
        )
        self.assertIn(
            "$data.gate.hand_mesh_runtime_clearance_solver_pass",
            self.wrapper,
        )
        self.assertNotIn(
            "$data.gate.hand_mesh_wrist_realization_pass",
            self.wrapper,
        )
        self.assertIn(
            "$data.gate.middle_bone_tip_diagnostic_recorded",
            self.wrapper,
        )
        self.assertNotIn(
            "$data.gate.fingertip_centerline_spacing_pass",
            self.wrapper,
        )

    def test_wrapper_is_fail_closed_against_stale_report(self) -> None:
        self.assertIn(
            "Remove-Item -Force $output",
            self.wrapper,
        )
        self.assertIn(
            "--python-exit-code 1",
            self.wrapper,
        )

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
