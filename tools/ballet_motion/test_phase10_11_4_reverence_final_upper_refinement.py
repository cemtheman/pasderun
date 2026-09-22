from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
TOOLS=REPO/"tools"/"ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))

import opening_reverence_final_upper_refinement as refinement  # noqa: E402


class Phase10114ReverenceFinalUpperTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "opening_reverence_final_upper_refinement_contract_v1.json"
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

    def test_selected_reverence_authority_is_forward_30(self) -> None:
        selected=self.contract["upper_body"]["selected_reverence_authority"]
        self.assertEqual(
            selected["mode"],
            "EXPLICIT_REVERENCE_GAP_WITH_SEMANTIC_CARRIAGE",
        )
        self.assertEqual(selected["source_pose"],"bras_bas")
        self.assertEqual(selected["reference_pose"],"en_avant")
        self.assertEqual(
            selected["target_gap_shoulder_width_fraction"],0.36
        )
        self.assertEqual(selected["carriage_progress"],0.30)
        self.assertEqual(
            selected["elbow_pole_policy"],"EXACT_BRAS_BAS"
        )
        self.assertEqual(
            selected["joint_dofs_policy"],"EXACT_BRAS_BAS"
        )
        self.assertEqual(
            selected["gap_authority"],
            "DEFORMED_HAND_MESH_PRIMARY_SHOULDER_SWEEP",
        )
        self.assertEqual(
            selected["human_visual_selection"],"forward_30"
        )

    def test_endpoint_interpolation_is_diagnostic_reference_only(self) -> None:
        a=self.contract["upper_body"]["arm_source_authority"]
        self.assertTrue(a["diagnostic_reference_only"])
        self.assertEqual(a["start_pose"],"bras_bas")
        self.assertEqual(a["upper_bound_reference_pose"],"en_avant")

    def test_bow_is_stronger_but_bounded(self) -> None:
        bow=self.contract["upper_body"]["bow"]
        self.assertEqual(bow["canonical_axis"],"X")
        self.assertGreater(bow["trunk_extra_flexion_deg"],10.0)
        self.assertLessEqual(bow["trunk_extra_flexion_deg"],28.0)
        self.assertLessEqual(bow["neck_flexion_deg"],8.0)
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
            v["selected_explicit_reverence_authority_required"]
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
