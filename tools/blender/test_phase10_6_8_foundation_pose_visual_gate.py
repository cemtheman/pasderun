import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]
CONTRACT = (
    ROOT
    / "assets"
    / "ballet_motion"
    / "foundation_pose_visual_gate_v1.json"
)
SCRIPT = (
    ROOT
    / "tools"
    / "blender"
    / "render_foundation_pose_visual_gate_v1.py"
)
WRAPPER = (
    ROOT
    / "tools"
    / "blender"
    / "run_phase10_6_8_foundation_pose_visual_gate.ps1"
)


class Phase1068FoundationPoseVisualGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(
            CONTRACT.read_text(encoding="utf-8")
        )
        cls.script = SCRIPT.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_contract_is_phase_10_6_8(self) -> None:
        self.assertEqual(self.contract["phase"], "10.6.8")
        self.assertEqual(
            self.contract["contract_id"],
            "foundation_pose_visual_gate_v1",
        )

    def test_exact_foundation_pose_set(self) -> None:
        self.assertEqual(
            self.contract["poses"],
            [
                "bras_bas",
                "en_avant",
                "second",
                "fifth",
                "plie",
                "releve",
            ],
        )

    def test_exact_three_view_set(self) -> None:
        self.assertEqual(
            self.contract["views"],
            ["FRONT", "THREE_QUARTER", "SIDE"],
        )
        self.assertEqual(
            self.contract["render"]["contact_sheet_rows"],
            6,
        )
        self.assertEqual(
            self.contract["render"]["contact_sheet_columns"],
            3,
        )

    def test_human_visual_acceptance_is_mandatory(self) -> None:
        policy = self.contract["policy"]
        self.assertTrue(policy["human_visual_acceptance_required"])
        self.assertTrue(
            policy["automated_ballet_aesthetic_pass_forbidden"]
        )
        self.assertIn(
            '"status": "PENDING_REVIEW"',
            self.script,
        )

    def test_no_animation_or_glb_export(self) -> None:
        policy = self.contract["policy"]
        self.assertTrue(policy["animation_forbidden"])
        self.assertTrue(policy["glb_export_forbidden"])
        self.assertNotIn("export_scene.gltf", self.script)
        self.assertNotIn("keyframe_insert", self.script)

    def test_old_motion_authoring_is_not_imported(self) -> None:
        self.assertNotIn(
            "build_ballet_pose_lab_v1",
            self.script,
        )
        self.assertNotIn(
            "build_opening_reverence_v1",
            self.script,
        )
        self.assertNotIn(
            "apply_arm_landmark_pose",
            self.script,
        )
        self.assertIn(
            "import apply_static_foundation_poses_v1 as static_core",
            self.script,
        )

    def test_wrist_continuity_forbids_independent_axial_roll(self) -> None:
        wrist = self.contract["wrist_continuity"]
        self.assertTrue(
            wrist["independent_axial_y_rotation_forbidden"]
        )
        self.assertEqual(
            wrist["local_dof_composition"],
            "Rx(flexion_extension) then Rz(radial_ulnar_deviation)",
        )
        self.assertIn(
            "def decompose_wrist_xz(",
            self.script,
        )
        self.assertIn(
            "hand frame requires undeclared axial wrist",
            self.script,
        )

    def test_wrist_continuity_uses_preferred_10_6_3_limits(self) -> None:
        self.assertEqual(
            self.contract["wrist_continuity"]["limit_source"],
            "Phase 10.6.3 wrist_2dof preferred envelope",
        )
        self.assertIn(
            'limits = constraints["joint_limits"]["wrist_2dof"]["dofs"]',
            self.script,
        )
        self.assertIn(
            'preferred = limits[dof_name]["preferred"]',
            self.script,
        )

    def test_wrist_limit_comparison_tolerance_is_tight_and_explicit(self) -> None:
        tolerance = self.contract["wrist_continuity"][
            "limit_comparison_tolerance_deg"
        ]
        self.assertEqual(tolerance, 0.001)
        self.assertIn(
            '"limit_comparison_tolerance_deg"',
            self.script,
        )
        self.assertIn(
            "minimum - comparison_tolerance_deg",
            self.script,
        )
        self.assertIn(
            "maximum + comparison_tolerance_deg",
            self.script,
        )
        self.assertIn(
            "Wrist limit comparison tolerance must remain <= 0.001 degree.",
            self.script,
        )

    def test_hand_gate_runs_only_on_upper_body_foundation_poses(self) -> None:
        self.assertIn(
            'if pose_name in ("bras_bas", "en_avant", "second"):',
            self.script,
        )
        self.assertIn(
            "validate_hand_axial_continuity(",
            self.script,
        )

    def test_every_pose_is_realized_before_render(self) -> None:
        realize_index = self.script.index("realization = realize_pose(")
        render_index = self.script.index("cell = render_cell(")
        self.assertLess(realize_index, render_index)
        self.assertIn(
            "mesh contact failed before render",
            self.script,
        )

    def test_full_foot_realization_reuses_10_6_7_authority(self) -> None:
        self.assertIn(
            "static_core.realize_full_foot_orientation(",
            self.script,
        )
        self.assertIn(
            "static_core.root_shift_for_contact(",
            self.script,
        )
        self.assertIn(
            "static_core.set_root_translation_armature_space(",
            self.script,
        )

    def test_releve_realization_reuses_10_6_7_authority(self) -> None:
        self.assertIn(
            "static_core.solve_releve_plantar_toe_for_mesh_heel_height(",
            self.script,
        )
        self.assertIn(
            "releve_toe_search_coarse_step_deg",
            self.script,
        )
        self.assertIn(
            "releve_joint_search_refine_steps_deg",
            self.script,
        )
        self.assertIn(
            "left_heel_height",
            self.script,
        )
        self.assertIn(
            "right_heel_height",
            self.script,
        )

    def test_deformed_hand_mesh_spacing_is_final_authority_before_render(self) -> None:
        self.assertIn(
            "static_core.hand_rig_vertex_groups(",
            self.script,
        )
        self.assertNotIn(
            'canonical["canonical_bones"]["left_middle"]["rig_bone"],',
            self.script,
        )
        self.assertIn(
            "static_core.solve_runtime_hand_mesh_pose(",
            self.script,
        )
        self.assertIn(
            'hand_mesh_runtime_solution["status"] == "PASS"',
            self.script,
        )
        self.assertIn(
            '"hand_mesh_runtime_clearance_solution"',
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
        self.assertIn(
            '"hand_mesh_runtime_clearance_solver_pass": True',
            self.script,
        )
        self.assertNotIn(
            "static_core.solve_hand_mesh_wrist_spacing(",
            self.script,
        )

    def test_middle_fingertip_spacing_is_diagnostic_only(self) -> None:
        self.assertIn(
            "static_core.realized_middle_fingertip_spacing(",
            self.script,
        )
        self.assertIn(
            '"fingertip_spacing_diagnostic": fingertip_spacing',
            self.script,
        )
        self.assertIn(
            '"middle_bone_tip_diagnostic_recorded": True',
            self.script,
        )
        self.assertNotIn(
            'fingertip_spacing["status"] == "PASS"',
            self.script,
        )

    def test_render_count_is_exactly_eighteen(self) -> None:
        self.assertIn(
            '"render_count": len(pose_names) * len(view_names)',
            self.script,
        )
        self.assertIn(
            'print("RENDERS=18")',
            self.script,
        )
        self.assertIn(
            'if ($data.render_count -ne 18)',
            self.wrapper,
        )

    def test_identical_orthographic_camera_contract(self) -> None:
        self.assertTrue(
            self.contract["render"]["identical_orthographic_scale"]
        )
        self.assertIn(
            'camera_data.type = "ORTHO"',
            self.script,
        )
        self.assertIn(
            "camera_data.ortho_scale = height * 1.14",
            self.script,
        )

    def test_front_three_quarter_side_camera_are_declared_frame_based(self) -> None:
        self.assertIn(
            'Vector(frame["front"])',
            self.script,
        )
        self.assertIn(
            'Vector(frame["left"])',
            self.script,
        )
        self.assertIn(
            'Vector(frame["up"])',
            self.script,
        )
        self.assertIn(
            'view_name == "THREE_QUARTER"',
            self.script,
        )

    def test_contact_sheet_preserves_individual_cells(self) -> None:
        self.assertTrue(
            self.contract["render"]["individual_cells_preserved"]
        )
        self.assertIn(
            'output_dir = output_path.parent / "foundation_pose_cells"',
            self.script,
        )
        self.assertIn(
            "save_contact_sheet(",
            self.script,
        )

    def test_wrapper_refreshes_stale_pose_and_retarget_profile(self) -> None:
        self.assertIn(
            "Get-FileHash -Algorithm SHA256",
            self.wrapper,
        )
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
            "Refreshing Phase 10.6.6 retarget prerequisite",
            self.wrapper,
        )

    def test_wrapper_is_fail_closed_against_stale_visual_artifacts(self) -> None:
        self.assertIn(
            "Remove-Item -Force $stale",
            self.wrapper,
        )
        self.assertIn(
            "Remove-Item -Recurse -Force $cellDir",
            self.wrapper,
        )
        self.assertIn(
            "--python-exit-code 1",
            self.wrapper,
        )

    def test_wrapper_requires_hand_mesh_spacing_and_wrist_seed_gates(self) -> None:
        self.assertIn(
            "$data.automated_gate.hand_mesh_centerline_spacing_pass",
            self.wrapper,
        )
        self.assertIn(
            "$data.automated_gate.hand_mesh_retarget_wrist_seed_preserved_pass",
            self.wrapper,
        )
        self.assertNotIn(
            "$data.automated_gate.hand_mesh_wrist_realization_pass",
            self.wrapper,
        )
        self.assertIn(
            "$data.automated_gate.hand_mesh_runtime_clearance_solver_pass",
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
            "$data.automated_gate.middle_bone_tip_diagnostic_recorded",
            self.wrapper,
        )
        self.assertNotIn(
            "$data.automated_gate.fingertip_centerline_spacing_pass",
            self.wrapper,
        )

    def test_wrapper_requires_pending_human_review(self) -> None:
        self.assertIn(
            '$data.human_visual_gate.status -ne "PENDING_REVIEW"',
            self.wrapper,
        )
        self.assertIn(
            "Machine may not decide the visual verdict.",
            self.wrapper,
        )

    def test_windows_wrapper_is_ascii_only(self) -> None:
        self.assertTrue(
            all(ord(char) < 128 for char in self.wrapper)
        )

    def test_visual_review_contract_covers_known_failure_modes(self) -> None:
        upper = " ".join(
            self.contract["visual_review_contract"]["upper_body"]
        ).lower()
        lower = " ".join(
            self.contract["visual_review_contract"]["lower_body"]
        ).lower()
        self.assertIn("flipped palm", upper)
        self.assertIn("shoulders", upper)
        self.assertIn("centerline", upper)
        self.assertIn("must not cross", upper)
        self.assertIn("squat/frog", lower)
        self.assertIn("full-foot contact", lower)
        self.assertIn("interpenetration", lower)
        self.assertIn("releve", lower)

    def test_visual_gate_does_not_write_aesthetic_accept(self) -> None:
        self.assertNotIn(
            '"status": "ACCEPT"',
            self.script,
        )
        self.assertNotIn(
            "AESTHETIC=PASS",
            self.script,
        )

    def test_output_contract_marks_machine_ready_not_visual_pass(self) -> None:
        self.assertIn(
            "PHASE10_6_8_FOUNDATION_POSE_VISUAL_GATE=READY",
            self.script,
        )
        self.assertIn(
            "HUMAN_VISUAL_ACCEPTANCE=PENDING",
            self.script,
        )


if __name__ == "__main__":
    unittest.main()
