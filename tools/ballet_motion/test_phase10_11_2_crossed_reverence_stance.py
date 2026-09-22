from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
TOOLS=REPO/"tools"/"ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))

import opening_reverence_crossed_stance as stance  # noqa: E402


class Phase10112CrossedReverenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "opening_reverence_crossed_stance_contract_v1.json"
            ).read_text(encoding="utf-8")
        )
        cls.constraints=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "anatomical_constraints_v1.json"
            ).read_text(encoding="utf-8")
        )

    def test_contract_is_valid(self) -> None:
        stance.validate_contract(self.contract)

    def test_asymmetric_side_assignment(self) -> None:
        sides=self.contract["side_assignment"]
        self.assertEqual(sides["support_side"],"left")
        self.assertEqual(sides["gesture_side"],"right")

    def test_candidate_search_is_small_and_deterministic(self) -> None:
        candidates=list(stance.candidate_parameter_sets(self.contract))
        self.assertEqual(len(candidates),27)
        self.assertEqual(candidates, list(stance.candidate_parameter_sets(self.contract)))

    def test_every_candidate_stays_in_preferred_joint_envelopes(self) -> None:
        for params in stance.candidate_parameter_sets(self.contract):
            state=stance.build_state(self.contract,params)
            self.assertEqual(
                stance.preferred_envelope_violations(
                    state,self.constraints
                ),
                [],
            )

    def test_gesture_leg_is_extension_adduction_and_plantarflexion(self) -> None:
        for params in stance.candidate_parameter_sets(self.contract):
            self.assertLess(params["gesture_hip_flexion_extension_deg"],0)
            self.assertLess(params["gesture_hip_abduction_adduction_deg"],0)
            self.assertGreater(
                params["gesture_ankle_plantar_dorsiflexion_deg"],0
            )

    def test_support_and_gesture_contacts_are_distinct(self) -> None:
        lower=self.contract["lower_body"]
        self.assertEqual(lower["support_contact"],"FULL_FOOT")
        self.assertEqual(
            lower["gesture_contact"],"FOREFOOT_OR_TOE_TOUCH"
        )

    def test_reference_geometry_gates_are_material(self) -> None:
        g=self.contract["geometry_targets"]
        self.assertGreaterEqual(g["gesture_cross_min_foot_fraction"],0.05)
        self.assertGreaterEqual(g["gesture_back_min_foot_fraction"],0.08)
        self.assertGreaterEqual(g["gesture_heel_lift_min_foot_fraction"],0.03)

    def test_scope_is_static_only(self) -> None:
        p=self.contract["policy"]
        self.assertTrue(p["static_pose_only"])
        self.assertTrue(p["animation_forbidden"])
        self.assertTrue(p["world_turn_forbidden"])
        self.assertTrue(p["run_handoff_forbidden"])
        self.assertTrue(p["music_sync_forbidden"])
        self.assertTrue(p["glb_export_forbidden"])


if __name__=="__main__":
    unittest.main()
