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
    _joint_delta,
    _rig_pose_from_canonical,
    _upper_limb_target_bases,
    _wrist_2dof_target_basis,
    validate_rest_identity,
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
CONSTRAINTS = ROOT / "assets" / "ballet_motion" / "anatomical_constraints_v1.json"
RETARGET = ROOT / "tools" / "ballet_motion" / "calibrated_rig_retarget.py"
BUILDER = ROOT / "tools" / "ballet_motion" / "build_calibrated_rig_retarget_v1.py"
WRAPPER = ROOT / "tools" / "ballet_motion" / "run_phase10_6_6_calibrated_rig_retarget.ps1"


class Phase1066CalibratedRigRetargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        cls.constraints = json.loads(
            CONSTRAINTS.read_text(encoding="utf-8")
        )
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
        self.assertEqual(
            hip["internal_external_rotation"]["scale"],
            -1,
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
        self.assertEqual(derived[0]["scale"], -1)
        self.assertTrue(derived[0]["side_sign"])

    def test_trunk_tilt_is_orientation_not_translation_passthrough(self) -> None:
        route = self.contract["scalar_orientation_routes"]["trunk_tilt_deg"]
        self.assertEqual(route["axis"], "X")
        self.assertAlmostEqual(
            sum(item["weight"] for item in route["routes"]),
            1.0,
            places=12,
        )
        self.assertEqual(
            {item["bone"] for item in route["routes"]},
            {"spine_lower", "spine_mid", "chest"},
        )
        self.assertIn('"scalar_orientation_routes"', self.retarget)
        self.assertIn('if key != "trunk_tilt_deg"', self.retarget)

    def test_trunk_tilt_route_executes_for_axial_ball(self) -> None:
        state = {"scalars": {"trunk_tilt_deg": 9.0}}
        bone = {"joint_class": "axial_ball"}
        delta = _joint_delta(
            "spine_lower",
            bone,
            state,
            self.contract,
        )
        self.assertGreater(matrix_max_error(delta, identity3()), 1e-6)
        self.assertLess(orthogonality_error(delta), 1e-12)
        self.assertAlmostEqual(determinant(delta), 1.0, places=12)

    def test_positive_turnout_rotates_both_feet_outward(self) -> None:
        axes = self.contract["lower_body_joint_axes"]
        hip_er = next(
            item
            for item in axes["hip_ball"]
            if item.get("dof") == "internal_external_rotation"
        )
        knee_er = next(
            item
            for item in axes["knee_hinge"]
            if item.get("derived") == "knee_external_rotation_deg"
        )

        # Canonical body coordinates are LEFT, UP, FRONT.
        pelvis = [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
        thigh_rest = [
            [-1.0, 0.0, 0.0],
            [0.0, -1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
        shin_rest = thigh_rest
        foot_rest = [
            [-1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0],
            [0.0, 1.0, 0.0],
        ]

        thigh_local_rest = mat_mul(transpose(pelvis), thigh_rest)
        shin_local_rest = mat_mul(
            transpose(thigh_rest),
            shin_rest,
        )
        foot_local_rest = mat_mul(
            transpose(shin_rest),
            foot_rest,
        )

        foot_left_components = None
        foot_right_components = None
        for side, side_factor in (("left", 1.0), ("right", -1.0)):
            hip_angle = (
                45.0
                * float(hip_er["scale"])
                * side_factor
            )
            knee_angle = (
                4.0
                * float(knee_er["scale"])
                * side_factor
            )
            thigh_pose = mat_mul(
                thigh_local_rest,
                axis_rotation("Y", hip_angle),
            )
            shin_pose = mat_mul(
                mat_mul(thigh_pose, shin_local_rest),
                axis_rotation("Y", knee_angle),
            )
            foot_pose = mat_mul(shin_pose, foot_local_rest)
            foot_forward = [
                foot_pose[row][1]
                for row in range(3)
            ]
            if side == "left":
                foot_left_components = foot_forward
            else:
                foot_right_components = foot_forward

        self.assertGreater(foot_left_components[0], 0.0)
        self.assertLess(foot_right_components[0], 0.0)
        self.assertGreater(foot_left_components[2], 0.0)
        self.assertGreater(foot_right_components[2], 0.0)

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

    def test_rest_identity_function_executes_on_synthetic_hierarchy(self) -> None:
        rest_root = identity3()
        rest_child = axis_rotation("Z", 20.0)
        rig_root = axis_rotation("X", 10.0)
        rig_child = mat_mul(rig_root, axis_rotation("Z", 20.0))

        def bone(parent, canonical_rest, rig_rest, name):
            bind = mat_mul(rig_rest, transpose(canonical_rest))
            return {
                "parent": parent,
                "rig_bone": name,
                "canonical_rest_contract": {
                    "basis_armature_local": canonical_rest,
                },
                "rig_rest_basis_armature_local": rig_rest,
                "retarget_bind": {
                    "canonical_to_rig_rotation_matrix": bind,
                },
            }

        profile = {
            "canonical_bones": {
                "pelvis": bone(
                    None,
                    rest_root,
                    rig_root,
                    "Pelvis",
                ),
                "child": bone(
                    "pelvis",
                    rest_child,
                    rig_child,
                    "Child",
                ),
            }
        }
        result = validate_rest_identity(profile, self.contract)
        self.assertLess(result["max_rig_rest_basis_error"], 1e-9)
        self.assertLess(
            result["max_local_delta_identity_error"],
            1e-9,
        )

    def test_rig_pose_function_executes_roundtrip_on_synthetic_hierarchy(self) -> None:
        rest_root = identity3()
        rest_child = axis_rotation("Z", 20.0)
        rig_root = axis_rotation("X", 10.0)
        rig_child = mat_mul(rig_root, axis_rotation("Z", 20.0))

        def bone(parent, canonical_rest, rig_rest, name):
            return {
                "parent": parent,
                "rig_bone": name,
                "canonical_rest_contract": {
                    "basis_armature_local": canonical_rest,
                },
                "rig_rest_basis_armature_local": rig_rest,
                "retarget_bind": {
                    "canonical_to_rig_rotation_matrix": mat_mul(
                        rig_rest,
                        transpose(canonical_rest),
                    ),
                },
            }

        profile = {
            "canonical_bones": {
                "pelvis": bone(None, rest_root, rig_root, "Pelvis"),
                "child": bone(
                    "pelvis",
                    rest_child,
                    rig_child,
                    "Child",
                ),
            }
        }
        canonical_pose = {
            "pelvis": axis_rotation("Y", 12.0),
            "child": mat_mul(
                axis_rotation("Y", 12.0),
                mat_mul(
                    axis_rotation("Z", 20.0),
                    axis_rotation("X", -8.0),
                ),
            ),
        }
        rig_pose, evidence = _rig_pose_from_canonical(
            canonical_pose,
            profile,
            self.contract["thresholds"],
        )
        self.assertEqual(set(rig_pose), {"pelvis", "child"})
        for item in evidence.values():
            self.assertLess(item["canonical_roundtrip_error"], 1e-9)
            self.assertLess(
                item["hierarchy_reconstruction_error"],
                1e-9,
            )

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

    def test_upper_limb_contract_uses_landmarks_and_declared_roll_authority(self) -> None:
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
        self.assertEqual(
            upper["hand"]["orientation_source"],
            "WRIST_LANDMARK_DIRECTION_SOLVED_IN_DECLARED_2DOF",
        )
        self.assertEqual(
            upper["hand"]["axial_roll_policy"],
            "NO_INDEPENDENT_HAND_AXIAL_ROLL",
        )
        semantic_policy = upper["hand"]["semantic_direction_policy"]
        self.assertTrue(
            semantic_policy.startswith(
                "SEMANTIC_PREFERENCE_CLAMPED_TO_WRIST_2DOF_PREFERRED_ENVELOPE"
            )
        )
        self.assertIn(
            "FINAL_CENTERLINE_SPACING_DEFERRED_TO_PHASE_10_6_7_DEFORMED_MESH",
            semantic_policy,
        )
        self.assertTrue(
            self.contract["policy"][
                "middle_fingertip_visual_spacing_gate_forbidden"
            ]
        )
        self.assertEqual(
            self.contract["policy"][
                "final_hand_centerline_spacing_authority"
            ],
            "Phase 10.6.7 deformed hand mesh",
        )
        self.assertEqual(
            upper["hand"]["limit_source"],
            "PHASE_10_6_3_WRIST_2DOF_PREFERRED",
        )
        self.assertIn("basis_from_length_and_front(", self.retarget)
        self.assertIn("local_twist_y(", self.retarget)
        self.assertIn("_wrist_2dof_target_basis(", self.retarget)

    def test_wrist_2dof_target_matches_landmark_without_axial_roll(self) -> None:
        parent_pose = mat_mul(
            axis_rotation("Y", 31.0),
            axis_rotation("X", -17.0),
        )
        parent_rest = identity3()
        hand_rest = identity3()

        intended_delta = mat_mul(
            axis_rotation("X", 18.0),
            axis_rotation("Z", -12.0),
        )
        intended_basis = mat_mul(parent_pose, intended_delta)
        direction = [
            intended_basis[row][1]
            for row in range(3)
        ]

        target, evidence = _wrist_2dof_target_basis(
            direction,
            parent_pose,
            parent_rest,
            hand_rest,
            self.constraints,
            self.contract,
        )
        recovered_local = mat_mul(
            transpose(parent_pose),
            target,
        )
        expected_local = intended_delta

        self.assertLess(
            matrix_max_error(recovered_local, expected_local),
            1e-10,
        )
        self.assertAlmostEqual(
            evidence["flexion_extension_deg"],
            18.0,
            places=8,
        )
        self.assertAlmostEqual(
            evidence["radial_ulnar_deviation_deg"],
            -12.0,
            places=8,
        )
        self.assertGreater(
            evidence["semantic_alignment_dot"],
            0.999999999,
        )

    def test_wrist_solver_clamps_semantic_direction_to_preferred_envelope(self) -> None:
        parent_pose = identity3()
        parent_rest = identity3()
        hand_rest = identity3()

        impossible_preferred = mat_mul(
            axis_rotation("X", 5.0),
            axis_rotation("Z", 29.0),
        )
        direction = [
            impossible_preferred[row][1]
            for row in range(3)
        ]

        target, evidence = _wrist_2dof_target_basis(
            direction,
            parent_pose,
            parent_rest,
            hand_rest,
            self.constraints,
            self.contract,
        )
        self.assertEqual(
            evidence["preferred_envelope_status"],
            "PASS",
        )
        self.assertLessEqual(
            evidence["radial_ulnar_deviation_deg"],
            20.0,
        )
        self.assertGreaterEqual(
            evidence["radial_ulnar_deviation_deg"],
            -25.0,
        )
        self.assertGreater(
            evidence["semantic_alignment_dot"],
            0.98,
        )
        recovered_y = normalize(
            [target[row][1] for row in range(3)]
        )
        self.assertGreater(
            sum(
                recovered_y[index] * direction[index]
                for index in range(3)
            ),
            0.98,
        )

    def test_hand_semantic_alignment_is_not_part_of_exact_arm_gate(self) -> None:
        self.assertIn(
            'if not name.endswith("_hand")',
            self.retarget,
        )
        self.assertIn(
            '"hand_semantic_direction_is_preference": True',
            self.retarget,
        )
        self.assertIn(
            '"hand_wrist_preferred_envelope_pass": True',
            self.retarget,
        )

    def test_hand_basis_is_not_reseeded_from_body_front(self) -> None:
        start = self.retarget.index('if role == "hand":')
        end = self.retarget.index(
            "\n            else:",
            start,
        )
        hand_path = self.retarget[start:end]
        self.assertIn(
            "_wrist_2dof_target_basis(",
            hand_path,
        )
        self.assertNotIn(
            "basis_from_length_and_front(",
            hand_path,
        )
        self.assertNotIn(
            "local_twist_y(",
            hand_path,
        )

    def test_semantic_limb_retarget_preserves_solved_length_axis(self) -> None:
        self.assertTrue(
            self.contract["policy"][
                "semantic_limb_length_axis_preservation_required"
            ]
        )
        self.assertTrue(
            self.contract["policy"][
                "rest_bind_swing_may_not_rotate_solved_limb_length_axis"
            ]
        )
        self.assertEqual(
            self.contract["thresholds"][
                "semantic_limb_length_axis_alignment_min_dot"
            ],
            0.99999,
        )
        self.assertIn(
            "def _semantic_roll_offset_y(",
            self.retarget,
        )
        self.assertIn(
            '"SEMANTIC_LENGTH_AXIS_PRESERVED"',
            self.retarget,
        )
        self.assertIn(
            "semantic_limb_length_axis_preservation_pass",
            self.retarget,
        )

    def test_semantic_mapping_uses_only_local_y_roll_not_full_bind_swing(self) -> None:
        start = self.retarget.index(
            "def _rig_target_from_canonical_pose("
        )
        end = self.retarget.index(
            "def _canonical_roundtrip_from_rig_target(",
            start,
        )
        source = self.retarget[start:end]
        self.assertIn(
            'axis_rotation("Y", roll_deg)',
            source,
        )
        self.assertNotIn(
            "mat_mul(_bind_basis(bone), canonical_pose)",
            source.split(
                'return desired, "SEMANTIC_LENGTH_AXIS_PRESERVED"'
            )[0],
        )

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
            "hand_mesh_spacing_contract",
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

    def test_builder_passes_constraint_profile_into_retarget(self) -> None:
        self.assertIn(
            "canonical,\n            constraints,\n            contract,",
            self.builder,
        )
        self.assertIn(
            '"hand_wrist_preferred_envelope_pass": True',
            self.builder,
        )

    def test_wrapper_requires_hand_wrist_preferred_envelope_gate(self) -> None:
        self.assertIn(
            "$data.gate.hand_wrist_preferred_envelope_pass",
            self.wrapper,
        )
        self.assertIn(
            "Hand wrist preferred-envelope gate failed.",
            self.wrapper,
        )
        self.assertIn(
            "$data.gate.semantic_limb_length_axis_preservation_pass",
            self.wrapper,
        )
        self.assertIn(
            "Semantic limb length-axis preservation gate failed.",
            self.wrapper,
        )

    def test_middle_fingertip_visual_gate_is_deferred_to_blender_mesh(self) -> None:
        self.assertTrue(
            self.contract["policy"][
                "middle_fingertip_visual_spacing_gate_forbidden"
            ]
        )
        self.assertEqual(
            self.contract["policy"][
                "final_hand_centerline_spacing_authority"
            ],
            "Phase 10.6.7 deformed hand mesh",
        )
        self.assertNotIn(
            "calibrated_middle_fingertip_spacing_pass",
            self.builder,
        )
        self.assertNotIn(
            "$data.gate.calibrated_middle_fingertip_spacing_pass",
            self.wrapper,
        )
        self.assertNotIn(
            "CALIBRATED_MIDDLE_FINGERTIP_SPACING=PASS",
            self.builder,
        )
        self.assertNotIn(
            "_middle_fingertip_context(",
            self.retarget,
        )
        self.assertNotIn(
            "_middle_fingertip_from_hand_target(",
            self.retarget,
        )

    def test_output_tracks_retarget_source_sha(self) -> None:
        self.assertIn(
            '"retarget_source_sha256"',
            self.builder,
        )
        self.assertIn(
            "retarget_source_path = Path(__file__).with_name(",
            self.builder,
        )
        self.assertIn(
            '"calibrated_rig_retarget.py"',
            self.builder,
        )

    def test_wrapper_refreshes_10_6_5_when_intent_spec_changes(self) -> None:
        self.assertIn(
            "run_phase10_6_5_canonical_pose_solver.ps1",
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
            "Phase 10.6.5 pose profile is stale; intent spec changed.",
            self.wrapper,
        )
        self.assertIn(
            "Phase 10.6.5 pose profile is stale; solver source changed.",
            self.wrapper,
        )
        self.assertIn(
            "Refreshing Phase 10.6.5 pose prerequisite",
            self.wrapper,
        )

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
