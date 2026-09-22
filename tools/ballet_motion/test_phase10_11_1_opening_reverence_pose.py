from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
TOOLS=REPO/"tools"/"ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))

import opening_reverence_pose as pose  # noqa: E402


class Phase10111OpeningReverencePoseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "opening_reverence_pose_contract_v1.json"
            ).read_text(encoding="utf-8")
        )

    def test_contract_is_valid(self) -> None:
        pose.validate_contract(self.contract)

    def test_uses_accepted_plie_and_second(self) -> None:
        source=self.contract["source_pose_authority"]
        self.assertEqual(source["lower_body_pose"],"plie")
        self.assertEqual(source["arm_pose"],"second")
        self.assertEqual(
            source["explicit_arm_chain_local_matrix_authority"],
            "EXACT_ACCEPTED_SECOND",
        )

    def test_no_new_arm_or_leg_authoring(self) -> None:
        overlay=self.contract["acknowledgement_overlay"]
        self.assertTrue(
            overlay["independently_authored_arm_rotation_forbidden"]
        )
        self.assertTrue(
            overlay["independently_authored_leg_rotation_forbidden"]
        )

    def test_axial_overlay_is_small_and_canonical(self) -> None:
        overlay=self.contract["acknowledgement_overlay"]
        self.assertEqual(overlay["canonical_axis"],"X")
        self.assertLessEqual(overlay["trunk_extra_flexion_deg"],8.0)
        self.assertLessEqual(overlay["neck_flexion_deg"],3.0)
        self.assertLessEqual(overlay["head_flexion_deg"],5.0)

    def test_matrix_and_contact_gates_are_strict(self) -> None:
        v=self.contract["validation"]
        self.assertLessEqual(
            v["lower_contact_chain_local_matrix_error_max"],1e-6
        )
        self.assertLessEqual(
            v["arm_explicit_chain_local_matrix_error_max"],1e-6
        )
        self.assertTrue(v["full_foot_contact_required"])
        self.assertTrue(v["hand_centerline_crossing_forbidden"])

    def test_front_view_is_audience_view(self) -> None:
        facing=self.contract["facing"]
        self.assertEqual(
            facing["audience_direction_authority"],
            "CANONICAL_BODY_FRAME_FRONT",
        )
        self.assertTrue(facing["preview_front_is_audience_view"])
        self.assertTrue(facing["godot_orientation_integration_deferred"])

    def test_animation_and_runtime_scope_are_deferred(self) -> None:
        p=self.contract["policy"]
        self.assertTrue(p["static_pose_only"])
        self.assertTrue(p["animation_forbidden"])
        self.assertTrue(p["world_turn_forbidden"])
        self.assertTrue(p["run_handoff_forbidden"])
        self.assertTrue(p["music_sync_forbidden"])
        self.assertTrue(p["glb_export_forbidden"])


if __name__=="__main__":
    unittest.main()
