from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
TOOLS=REPO/"tools"/"ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))

import foundation_motion_composition as composition  # noqa: E402


class Phase1091FoundationCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "foundation_motion_composition_contract_v1.json"
            ).read_text(encoding="utf-8")
        )
        cls.first=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "foundation_motion_contract_v1.json"
            ).read_text(encoding="utf-8")
        )
        cls.second=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "foundation_motion_en_avant_to_second_v1.json"
            ).read_text(encoding="utf-8")
        )

    def test_contract_and_total_frame_count(self) -> None:
        composition.validate_contract(self.contract)
        self.assertEqual(composition.expected_frame_count(self.contract),121)
        self.assertEqual(composition.segment_frame_counts(self.contract),(61,60))

    def test_source_contract_ids_are_exact(self) -> None:
        sequence=self.contract["sequence"]
        self.assertEqual(
            sequence[0]["source_contract_id"],
            self.first["contract_id"],
        )
        self.assertEqual(
            sequence[1]["source_contract_id"],
            self.second["contract_id"],
        )
        self.assertEqual(self.first["phase"],"10.7.1")
        self.assertEqual(self.second["phase"],"10.7.2")

    def test_shared_pose_and_frame_are_exact(self) -> None:
        first,second=self.contract["sequence"]
        self.assertEqual(first["end_pose"],"en_avant")
        self.assertEqual(second["start_pose"],"en_avant")
        self.assertEqual(first["frame_end"],61)
        self.assertEqual(second["frame_start"],61)
        self.assertEqual(
            self.contract["timeline"]["inserted_hold_frames"],
            0,
        )

    def test_composition_does_not_redefine_primitive_math(self) -> None:
        authority=self.contract["authority"]
        self.assertTrue(authority["composition_only"])
        self.assertTrue(
            authority["source_primitive_math_reimplementation_forbidden"]
        )
        self.assertEqual(
            authority["source_primitive_modules_required"],
            [
                "build_foundation_transition_v1",
                "build_foundation_transition_en_avant_to_second_v1",
            ],
        )

    def test_gates_remain_strict(self) -> None:
        validation=self.contract["validation"]
        self.assertLessEqual(
            validation["shared_boundary_local_matrix_error_max"],1e-6
        )
        self.assertLessEqual(
            validation["boundary_output_local_matrix_error_max"],1e-6
        )
        self.assertLessEqual(
            validation["lower_body_locked_local_matrix_error_max"],1e-6
        )
        self.assertTrue(validation["sample_every_frame"])
        self.assertTrue(validation["no_duplicate_boundary_key_authority"])

    def test_scope_excludes_later_integration(self) -> None:
        policy=self.contract["policy"]
        self.assertTrue(policy["lower_body_composition_forbidden"])
        self.assertTrue(policy["reverence_forbidden"])
        self.assertTrue(policy["run_integration_forbidden"])
        self.assertTrue(policy["music_sync_forbidden"])
        self.assertTrue(policy["gameplay_changes_forbidden"])
        self.assertTrue(policy["full_choreography_forbidden"])


if __name__=="__main__":
    unittest.main()
