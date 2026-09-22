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
        cls.constraints=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "anatomical_constraints_v1.json"
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

    def test_every_arm_candidate_is_in_preferred_envelope(self) -> None:
        for params in refinement.arm_candidate_parameter_sets(self.contract):
            state=refinement.build_arm_state(self.contract,params)
            self.assertEqual(
                refinement.preferred_envelope_violations(
                    state,self.constraints
                ),
                [],
            )

    def test_search_stays_below_second_position_guard(self) -> None:
        maximum=max(
            p["upper_arm_abduction_adduction_deg"]
            for p in refinement.arm_candidate_parameter_sets(self.contract)
        )
        self.assertLessEqual(maximum,50.0)
        self.assertLess(maximum,90.0)

    def test_bow_is_stronger_but_bounded(self) -> None:
        bow=self.contract["upper_body"]["bow"]
        self.assertEqual(bow["canonical_axis"],"X")
        self.assertGreater(bow["trunk_extra_flexion_deg"],10.0)
        self.assertLessEqual(bow["trunk_extra_flexion_deg"],20.0)
        self.assertLessEqual(bow["neck_flexion_deg"],6.0)
        self.assertLessEqual(bow["head_flexion_deg"],10.0)

    def test_hand_gap_target_has_breathing_room(self) -> None:
        g=self.contract["visual_geometry_targets"]
        self.assertGreaterEqual(g["hand_gap_hand_chain_fraction_min"],0.15)
        self.assertGreater(
            g["hand_gap_hand_chain_fraction_ideal"],
            g["hand_gap_hand_chain_fraction_min"],
        )
        self.assertLessEqual(
            g["hand_side_offset_asymmetry_hand_chain_fraction_max"],
            0.15,
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
