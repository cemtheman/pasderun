import json
import pathlib
import unittest

from canonical_pose_solver import (
    PoseSolveRejected,
    apply_rejection_probe,
    evaluate_rejection_probe,
    solve_pose,
)


ROOT = pathlib.Path(__file__).resolve().parents[2]
INTENTS = ROOT / "assets" / "ballet_motion" / "foundation_pose_intents_v1.json"
GRAMMAR = ROOT / "assets" / "ballet_motion" / "ballet_pose_grammar_v1.json"
CONSTRAINTS = ROOT / "assets" / "ballet_motion" / "anatomical_constraints_v1.json"
CANONICAL_SPEC = ROOT / "assets" / "ballet_motion" / "canonical_ballet_skeleton_v1.json"
SOLVER = ROOT / "tools" / "ballet_motion" / "canonical_pose_solver.py"
BUILDER = ROOT / "tools" / "ballet_motion" / "build_canonical_pose_solver_v1.py"
WRAPPER = ROOT / "tools" / "ballet_motion" / "run_phase10_6_5_canonical_pose_solver.ps1"


def synthetic_canonical_profile(canonical_spec: dict) -> dict:
    joint_classes = {
        name: spec["joint_class"]
        for name, spec in canonical_spec["bones"].items()
    }
    lengths = {
        "left_upper_arm": 0.30,
        "right_upper_arm": 0.30,
        "left_forearm": 0.28,
        "right_forearm": 0.28,
        "left_hand": 0.10,
        "right_hand": 0.10,
        "left_middle": 0.06,
        "right_middle": 0.06,
        "left_foot": 0.22,
        "right_foot": 0.22,
        "left_toes": 0.10,
        "right_toes": 0.10,
    }
    bones = {}
    for name in canonical_spec["bones"]:
        length = lengths.get(name, 0.20)
        head = {"left": 0.0, "up": 0.8, "front": 0.0}
        if name == "left_upper_arm":
            head = {"left": 0.35, "up": 1.40, "front": 0.0}
        elif name == "right_upper_arm":
            head = {"left": -0.35, "up": 1.40, "front": 0.0}
        elif name == "head":
            head = {"left": 0.0, "up": 1.72, "front": 0.0}
        elif name in ("left_foot", "right_foot"):
            head = {"left": 0.0, "up": 0.0, "front": 0.0}
        bones[name] = {
            "joint_class": joint_classes[name],
            "length": length,
            "head_body": head,
        }
    return {
        "phase": "10.6.2",
        "profile_id": "synthetic",
        "source": {"sha256": "synthetic"},
        "canonical_bones": bones,
    }


def synthetic_constraint_profile(
    constraint_source: dict,
    canonical_spec: dict,
) -> dict:
    return {
        **constraint_source,
        "phase": "10.6.3",
        "profile_id": "synthetic_constraints",
        "bone_constraints": {
            name: {
                "joint_class": spec["joint_class"],
                "limits": constraint_source["joint_limits"][spec["joint_class"]],
            }
            for name, spec in canonical_spec["bones"].items()
        },
    }


class Phase1065CanonicalPoseSolverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.intents = json.loads(INTENTS.read_text(encoding="utf-8"))
        cls.grammar_source = json.loads(GRAMMAR.read_text(encoding="utf-8"))
        cls.constraint_source = json.loads(CONSTRAINTS.read_text(encoding="utf-8"))
        cls.canonical_spec = json.loads(CANONICAL_SPEC.read_text(encoding="utf-8"))
        cls.canonical = synthetic_canonical_profile(cls.canonical_spec)
        cls.constraints = synthetic_constraint_profile(
            cls.constraint_source,
            cls.canonical_spec,
        )
        cls.grammar = {
            **cls.grammar_source,
            "phase": "10.6.4",
            "validation": {"arms_behind_back_is_blocked": True},
        }
        cls.solver = SOLVER.read_text(encoding="utf-8")
        cls.builder = BUILDER.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")

    def test_exact_foundation_pose_set(self) -> None:
        self.assertEqual(
            set(self.intents["poses"]),
            {"bras_bas", "en_avant", "second", "fifth", "plie", "releve"},
        )

    def test_solver_does_not_read_reference_fixture_coordinates(self) -> None:
        self.assertNotIn("ballet_pose_fixtures_v1", self.solver)
        self.assertNotIn("bras_bas_valid", self.solver)
        self.assertEqual(
            self.intents["policy"]["source_of_pose_intent"],
            "semantic_parameters_not_reference_fixture_coordinates",
        )

    def test_three_arm_poses_solve_and_pass_geometry(self) -> None:
        for pose in ("bras_bas", "en_avant", "second"):
            result = solve_pose(
                pose,
                self.intents,
                self.grammar,
                self.canonical,
                self.constraints,
            )
            self.assertEqual(result["validation"]["status"], "PASS")
            self.assertEqual(
                result["evidence"]["preferred_joint_envelope"],
                "PASS",
            )

    def test_semantic_intent_does_not_tighten_hard_front_grammar(self) -> None:
        for pose in ("bras_bas", "en_avant", "second"):
            intent = self.intents["poses"][pose]
            self.assertNotIn("minimum_wrist_front_margin", intent)
            self.assertNotIn("minimum_elbow_front_margin", intent)
        self.assertNotIn("minimum_wrist_front_margin", self.solver)
        self.assertNotIn("minimum_elbow_front_margin", self.solver)
        self.assertIn(
            "Grammar owns the hard anterior boundary",
            self.solver,
        )

    def test_wrist_target_is_preference_not_single_hard_ray(self) -> None:
        self.assertIn("def _wrist_constraints(", self.solver)
        self.assertIn("def _wrist_satisfies_constraints(", self.solver)
        self.assertIn("def _candidate_unit_directions(", self.solver)
        self.assertIn("Deterministic Fibonacci sphere", self.solver)
        self.assertIn(
            "semantic intent remains the preference while grammar decides feasibility",
            " ".join(
                line.strip().lstrip("#").strip()
                for line in self.solver.splitlines()
            ),
        )

    def test_solver_can_escape_infeasible_preferred_wrist_ray(self) -> None:
        altered = json.loads(json.dumps(self.intents))
        altered["poses"]["bras_bas"]["wrist_direction"] = {
            "inward": 0.98,
            "down": 0.05,
            "front": 0.05,
        }
        result = solve_pose(
            "bras_bas",
            altered,
            self.grammar,
            self.canonical,
            self.constraints,
        )
        self.assertEqual(result["validation"]["status"], "PASS")

    def test_arm_solver_enforces_grammar_lateral_order_across_ratios(self) -> None:
        variants = (
            (0.24, 0.30),
            (0.30, 0.28),
            (0.36, 0.24),
            (0.22, 0.34),
        )
        for upper_arm, forearm in variants:
            canonical = json.loads(json.dumps(self.canonical))
            for side in ("left", "right"):
                canonical["canonical_bones"][f"{side}_upper_arm"][
                    "length"
                ] = upper_arm
                canonical["canonical_bones"][f"{side}_forearm"][
                    "length"
                ] = forearm

            for pose in ("bras_bas", "en_avant", "second"):
                result = solve_pose(
                    pose,
                    self.intents,
                    self.grammar,
                    canonical,
                    self.constraints,
                )
                self.assertEqual(
                    result["validation"]["status"],
                    "PASS",
                    f"{pose} failed for arm ratio {upper_arm}/{forearm}",
                )

    def test_symmetric_arm_poses_are_exact_canonical_mirrors(self) -> None:
        for pose in ("bras_bas", "en_avant", "second"):
            result = solve_pose(
                pose,
                self.intents,
                self.grammar,
                self.canonical,
                self.constraints,
            )
            landmarks = result["state"]["landmarks"]
            for joint in ("shoulder", "elbow", "wrist", "hand"):
                left = landmarks[f"left_{joint}"]
                right = landmarks[f"right_{joint}"]
                self.assertAlmostEqual(
                    left["left"] + right["left"],
                    0.0,
                    places=12,
                )
                self.assertAlmostEqual(left["up"], right["up"], places=12)
                self.assertAlmostEqual(
                    left["front"],
                    right["front"],
                    places=12,
                )

    def test_bras_bas_and_en_avant_touch_not_cross_centerline(self) -> None:
        self.assertEqual(
            self.intents["poses"]["bras_bas"]["centerline_hand_policy"],
            "FINGERTIP_NEAR_TOUCH_NOT_CROSS",
        )
        self.assertEqual(
            self.intents["poses"]["en_avant"]["centerline_hand_policy"],
            "FINGERTIP_NEAR_TOUCH_NOT_CROSS",
        )
        for pose in ("bras_bas", "en_avant"):
            result = solve_pose(
                pose,
                self.intents,
                self.grammar,
                self.canonical,
                self.constraints,
            )
            landmarks = result["state"]["landmarks"]
            for side, sign in (("left", 1.0), ("right", -1.0)):
                self.assertGreaterEqual(
                    sign * float(landmarks[f"{side}_wrist"]["left"]),
                    -1e-9,
                )
                self.assertGreaterEqual(
                    sign * float(landmarks[f"{side}_hand"]["left"]),
                    -1e-9,
                )

    def test_bras_bas_and_en_avant_use_scale_relative_middle_fingertip_gap(self) -> None:
        for pose in ("bras_bas", "en_avant"):
            result = solve_pose(
                pose,
                self.intents,
                self.grammar,
                self.canonical,
                self.constraints,
            )
            state = result["state"]
            contract = state["fingertip_spacing_contract"]
            self.assertEqual(
                contract["scale_basis"],
                "average_hand_plus_middle_chain_length",
            )
            left_tip = state["landmarks"]["left_middle_tip"]
            right_tip = state["landmarks"]["right_middle_tip"]
            gap = float(left_tip["left"]) - float(right_tip["left"])
            self.assertGreater(gap, 0.0)
            self.assertGreaterEqual(gap + 1e-9, contract["minimum_gap"])
            self.assertLessEqual(gap, contract["maximum_gap"] + 1e-9)
            self.assertEqual(
                result["evidence"]["fingertip_spacing"]["status"],
                "PASS",
            )

    def test_middle_reference_is_not_an_articulated_finger_dof(self) -> None:
        result = solve_pose(
            "bras_bas",
            self.intents,
            self.grammar,
            self.canonical,
            self.constraints,
        )
        self.assertNotIn("left_middle", result["state"]["joint_dofs"])
        self.assertNotIn("right_middle", result["state"]["joint_dofs"])
        self.assertIn("left_middle_tip", result["state"]["landmarks"])
        self.assertIn("right_middle_tip", result["state"]["landmarks"])

    def test_second_has_no_fingertip_near_touch_contract(self) -> None:
        result = solve_pose(
            "second",
            self.intents,
            self.grammar,
            self.canonical,
            self.constraints,
        )
        self.assertNotIn("fingertip_spacing_contract", result["state"])

    def test_plie_travel_is_moderate_not_deep_crossing_setup(self) -> None:
        plie = self.intents["poses"]["plie"]
        self.assertLessEqual(plie["knee_flexion_deg"], 32)
        self.assertLessEqual(
            plie["joint_dofs"]["thigh"]["flexion_extension"],
            18,
        )
        self.assertLessEqual(
            plie["joint_dofs"]["thigh"]["abduction_adduction"],
            6,
        )
        self.assertLessEqual(
            plie["pelvis_descent_body_fraction"],
            0.065,
        )

    def test_arm_solver_preserves_segment_lengths(self) -> None:
        for pose in ("bras_bas", "en_avant", "second"):
            result = solve_pose(
                pose,
                self.intents,
                self.grammar,
                self.canonical,
                self.constraints,
            )
            evidence = result["evidence"]["arm_segment_lengths"]
            for side in ("left", "right"):
                self.assertLess(evidence[side]["upper_arm_error"], 1e-7)
                self.assertLess(evidence[side]["forearm_error"], 1e-7)

    def test_lower_body_foundation_poses_pass(self) -> None:
        for pose in ("fifth", "plie", "releve"):
            result = solve_pose(
                pose,
                self.intents,
                self.grammar,
                self.canonical,
                self.constraints,
            )
            self.assertEqual(result["validation"]["status"], "PASS")

    def test_solver_uses_grammar_constraints_not_only_preferred_pole(self) -> None:
        self.assertIn("def _arm_elbow_constraints(", self.solver)
        self.assertIn("def _elbow_satisfies_constraints(", self.solver)
        self.assertIn(
            "No exact two-bone elbow solution satisfies pose geometry",
            self.solver,
        )
        normalized_solver = " ".join(
            line.strip().lstrip("#").strip()
            for line in self.solver.splitlines()
        )
        self.assertIn(
            "grammar inequalities decide which geometric solutions are admissible",
            normalized_solver,
        )

    def test_foundation_pose_requires_preferred_not_soft_joint_envelope(self) -> None:
        self.assertTrue(
            self.intents["policy"][
                "foundation_gate_requires_preferred_joint_envelope"
            ]
        )
        bad = json.loads(json.dumps(self.intents))
        bad["poses"]["fifth"]["joint_dofs"]["thigh"][
            "internal_external_rotation"
        ] = 70
        with self.assertRaises(PoseSolveRejected):
            solve_pose(
                "fifth",
                bad,
                self.grammar,
                self.canonical,
                self.constraints,
            )

    def test_arms_behind_torso_probe_is_rejected(self) -> None:
        probe = self.intents["rejection_probes"]["arms_behind_torso"]
        result = evaluate_rejection_probe(
            probe,
            self.intents,
            self.grammar,
            self.canonical,
            self.constraints,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn(
            "anterior_halfspace",
            result["validation"]["failed_validators"],
        )

    def test_locked_t_pose_probe_is_rejected(self) -> None:
        probe = self.intents["rejection_probes"]["locked_t_pose"]
        result = evaluate_rejection_probe(
            probe,
            self.intents,
            self.grammar,
            self.canonical,
            self.constraints,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn(
            "wrist_below_shoulder",
            result["validation"]["failed_validators"],
        )

    def test_foot_yaw_probe_is_rejected(self) -> None:
        probe = self.intents["rejection_probes"]["independent_foot_yaw"]
        result = evaluate_rejection_probe(
            probe,
            self.intents,
            self.grammar,
            self.canonical,
            self.constraints,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn(
            "turnout_chain",
            result["validation"]["failed_validators"],
        )

    def test_com_outside_support_probe_is_rejected(self) -> None:
        probe = self.intents["rejection_probes"]["com_outside_support"]
        result = evaluate_rejection_probe(
            probe,
            self.intents,
            self.grammar,
            self.canonical,
            self.constraints,
        )
        self.assertEqual(result["status"], "REJECTED")
        self.assertIn(
            "support_polygon_com",
            result["validation"]["failed_validators"],
        )

    def test_solver_has_no_rig_blender_godot_or_render_scope(self) -> None:
        for forbidden in (
            "import bpy",
            "Skeleton3D",
            "AnimationTree",
            "humanoid_motion_controller.gd",
            "bpy.ops.",
        ):
            self.assertNotIn(forbidden, self.solver)
        self.assertTrue(self.intents["policy"]["rig_retarget_forbidden_in_this_phase"])
        self.assertTrue(self.intents["policy"]["render_forbidden_in_this_phase"])
        self.assertTrue(self.intents["policy"]["animation_forbidden_in_this_phase"])

    def test_builder_requires_all_six_and_all_rejection_probes(self) -> None:
        self.assertIn("all_pose_geometry_pass", self.builder)
        self.assertIn("all_pose_joint_dofs_preferred", self.builder)
        self.assertIn("all_invalid_probes_rejected", self.builder)
        self.assertIn("INVALID_PROBES=4/4_REJECTED", self.builder)

    def test_wrapper_auto_generates_10_6_4_prerequisite(self) -> None:
        self.assertIn(
            "run_phase10_6_4_ballet_pose_grammar.ps1",
            self.wrapper,
        )
        self.assertIn("generating prerequisite", self.wrapper)

    def test_wrapper_is_ascii_safe_for_windows_powershell(self) -> None:
        self.assertTrue(all(ord(char) < 128 for char in self.wrapper))

    def test_wrapper_enforces_no_retarget_render_or_animation(self) -> None:
        self.assertIn(
            "$data.foundation_gate.rig_retarget_performed",
            self.wrapper,
        )
        self.assertIn(
            "$data.foundation_gate.render_performed",
            self.wrapper,
        )
        self.assertIn(
            "$data.foundation_gate.animation_performed",
            self.wrapper,
        )

    def test_output_contract_is_phase_10_6_5(self) -> None:
        self.assertIn('PHASE = "10.6.5"', self.builder)
        self.assertIn(
            "PHASE10_6_5_CANONICAL_POSE_SOLVER=PASS",
            self.builder,
        )
        self.assertIn(
            "low_poly_girl_canonical_pose_solver_v1.json",
            self.wrapper,
        )


if __name__ == "__main__":
    unittest.main()
