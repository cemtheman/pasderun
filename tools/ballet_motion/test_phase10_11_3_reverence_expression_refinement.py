from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
TOOLS=REPO/"tools"/"ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))

import opening_reverence_expression_refinement as refinement  # noqa: E402


class Phase10113ReverenceExpressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "opening_reverence_expression_refinement_contract_v1.json"
            ).read_text(encoding="utf-8")
        )

    def test_contract_is_valid(self) -> None:
        refinement.validate_contract(self.contract)

    def test_frozen_lower_candidate_is_exact(self) -> None:
        self.assertEqual(
            self.contract["lower_body_authority"][
                "frozen_selected_parameters"
            ],
            {
                "gesture_hip_flexion_extension_deg":-10.0,
                "gesture_hip_abduction_adduction_deg":-20.0,
                "gesture_ankle_plantar_dorsiflexion_deg":44.0,
            },
        )

    def test_arm_search_is_nine_candidates(self) -> None:
        candidates=list(
            refinement.arm_candidate_parameter_sets(self.contract)
        )
        self.assertEqual(len(candidates),9)
        self.assertEqual(
            candidates,
            list(refinement.arm_candidate_parameter_sets(self.contract)),
        )

    def test_arm_authority_uses_accepted_endpoints(self) -> None:
        a=self.contract["upper_body"]["arm_source_authority"]
        self.assertEqual(a["start_pose"],"bras_bas")
        self.assertEqual(a["upper_bound_reference_pose"],"second")
        self.assertEqual(
            a["endpoint_authority"],
            "PHASE_10_6_ACCEPTED_REALIZATION",
        )
        self.assertEqual(
            a["shoulder_elbow_rotation"],
            "QUATERNION_SHORTEST_ARC_SLERP",
        )
        self.assertEqual(a["wrist_policy"],"EXACT_BRAS_BAS")
        self.assertEqual(a["fingers_policy"],"EXACT_BRAS_BAS")

    def test_search_stays_within_thirty_percent_of_second(self) -> None:
        candidates=list(
            refinement.arm_candidate_parameter_sets(self.contract)
        )
        self.assertLessEqual(
            max(p["shoulder_progress"] for p in candidates),
            0.30,
        )
        self.assertLessEqual(
            max(p["elbow_progress"] for p in candidates),
            0.30,
        )
        self.assertGreater(
            min(p["shoulder_progress"] for p in candidates),
            0.0,
        )
        self.assertEqual(
            sorted({p["shoulder_progress"] for p in candidates}),
            [0.08,0.10,0.12],
        )
        self.assertEqual(
            sorted({p["elbow_progress"] for p in candidates}),
            [0.15,0.20,0.25],
        )

    def test_bow_is_stronger_but_bounded(self) -> None:
        bow=self.contract["upper_body"]["bow"]
        self.assertEqual(bow["canonical_axis"],"X")
        self.assertGreater(bow["trunk_extra_flexion_deg"],10.0)
        self.assertLessEqual(bow["trunk_extra_flexion_deg"],24.0)
        self.assertLessEqual(bow["neck_flexion_deg"],7.0)
        self.assertLessEqual(bow["head_flexion_deg"],12.0)

    def test_hand_gap_target_uses_shoulder_midpoint_frame(self) -> None:
        g=self.contract["visual_geometry_targets"]
        self.assertEqual(
            g["metric_authority"],
            "SHOULDER_MIDPOINT_BODY_FRAME_LEFT_AXIS",
        )
        self.assertGreaterEqual(
            g["hand_gap_shoulder_width_fraction_min"],0.20
        )
        self.assertGreater(
            g["hand_gap_shoulder_width_fraction_ideal"],
            g["hand_gap_shoulder_width_fraction_min"],
        )
        self.assertLessEqual(
            g[
                "hand_midpoint_asymmetry_shoulder_width_fraction_max"
            ],
            0.10,
        )

    def test_no_centerline_projection_is_allowed(self) -> None:
        v=self.contract["validation"]
        self.assertTrue(v["no_centerline_projection_allowed"])
        self.assertTrue(
            v["accepted_arm_endpoint_bounded_interpolation_required"]
        )

    def test_scope_is_static_upper_refinement_only(self) -> None:
        p=self.contract["policy"]
        self.assertTrue(p["static_pose_only"])
        self.assertTrue(p["lower_body_redesign_forbidden"])
        self.assertTrue(p["animation_forbidden"])
        self.assertTrue(p["world_turn_forbidden"])
        self.assertTrue(p["run_handoff_forbidden"])
        self.assertTrue(p["music_sync_forbidden"])
        self.assertTrue(p["glb_export_forbidden"])


if __name__=="__main__":
    unittest.main()
