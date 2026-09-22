from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
TOOLS=REPO/"tools"/"ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))

import lower_body_motion_composition as composition  # noqa: E402


class Phase1092LowerCompositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "lower_body_motion_composition_contract_v1.json"
            ).read_text(encoding="utf-8")
        )
        cls.first=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "lower_body_foundation_motion_contract_v1.json"
            ).read_text(encoding="utf-8")
        )
        cls.second=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "lower_body_releve_motion_contract_v1.json"
            ).read_text(encoding="utf-8")
        )

    def test_contract_and_frame_count(self) -> None:
        composition.validate_contract(self.contract)
        self.assertEqual(composition.expected_frame_count(self.contract),121)
        self.assertEqual(composition.segment_frame_counts(self.contract),(61,60))

    def test_source_contracts_are_exact(self) -> None:
        sequence=self.contract["sequence"]
        self.assertEqual(
            sequence[0]["source_contract_id"],self.first["contract_id"]
        )
        self.assertEqual(
            sequence[1]["source_contract_id"],self.second["contract_id"]
        )
        self.assertEqual(self.first["phase"],"10.8.1")
        self.assertEqual(self.second["phase"],"10.8.2")

    def test_shared_plie_boundary_is_exact(self) -> None:
        first,second=self.contract["sequence"]
        self.assertEqual(first["end_pose"],"plie")
        self.assertEqual(second["start_pose"],"plie")
        self.assertEqual(first["frame_end"],61)
        self.assertEqual(second["frame_start"],61)
        self.assertEqual(
            self.contract["timeline"]["inserted_hold_frames"],0
        )

    def test_source_math_reimplementation_is_forbidden(self) -> None:
        authority=self.contract["authority"]
        self.assertTrue(authority["composition_only"])
        self.assertTrue(
            authority["source_primitive_math_reimplementation_forbidden"]
        )
        self.assertEqual(
            authority["source_primitive_modules_required"],
            [
                "build_lower_body_fifth_to_plie_v1",
                "build_lower_body_plie_to_releve_v1",
            ],
        )
        self.assertTrue(
            authority["accepted_trunk_hierarchy_motion_preserved"]
        )

    def test_contact_regime_is_source_defined(self) -> None:
        first,second=self.contract["sequence"]
        self.assertEqual(first["contact_mode"],"FULL_FOOT")
        self.assertEqual(
            second["contact_mode"],"FOREFOOT_AFTER_BOUNDARY"
        )

    def test_gates_remain_strict(self) -> None:
        v=self.contract["validation"]
        self.assertLessEqual(v["shared_boundary_local_matrix_error_max"],1e-6)
        self.assertLessEqual(v["boundary_output_local_matrix_error_max"],1e-6)
        self.assertLessEqual(v["root_horizontal_translation_max"],1e-5)
        self.assertTrue(v["sample_every_frame"])
        self.assertTrue(v["no_duplicate_boundary_key_authority"])

    def test_scope_excludes_later_integration(self) -> None:
        p=self.contract["policy"]
        self.assertTrue(p["arm_composition_changes_forbidden"])
        self.assertTrue(p["reverence_forbidden"])
        self.assertTrue(p["run_integration_forbidden"])
        self.assertTrue(p["music_sync_forbidden"])
        self.assertTrue(p["gameplay_changes_forbidden"])
        self.assertTrue(p["full_choreography_forbidden"])


if __name__=="__main__":
    unittest.main()
