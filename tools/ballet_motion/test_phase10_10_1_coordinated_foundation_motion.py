from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
TOOLS=REPO/"tools"/"ballet_motion"
if str(TOOLS) not in sys.path:
    sys.path.insert(0,str(TOOLS))

import coordinated_foundation_motion as motion  # noqa: E402


class Phase10101CoordinatedMotionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract=json.loads(
            (
                REPO/"assets"/"ballet_motion"/
                "coordinated_foundation_motion_contract_v1.json"
            ).read_text(encoding="utf-8")
        )

    def test_contract_and_frame_count(self) -> None:
        motion.validate_contract(self.contract)
        self.assertEqual(motion.expected_frame_count(self.contract),121)

    def test_chains_are_exact(self) -> None:
        self.assertEqual(
            self.contract["arm_chain"]["poses"],
            ["bras_bas","en_avant","second"],
        )
        self.assertEqual(
            self.contract["lower_chain"]["poses"],
            ["fifth","plie","releve"],
        )

    def test_single_boundary_and_no_hold(self) -> None:
        t=self.contract["timeline"]
        self.assertEqual(t["shared_boundary_frame"],61)
        self.assertEqual(t["inserted_hold_frames"],0)

    def test_authority_overlap_policy_is_explicit(self) -> None:
        a=self.contract["authority"]
        self.assertEqual(
            a["overlap_policy"],
            "ARM_EXPLICIT_MAY_OVERRIDE_LOWER_HIERARCHY_FOLLOWERS_ONLY",
        )
        self.assertTrue(
            a["lower_semantic_driver_overlap_with_arm_forbidden"]
        )
        self.assertEqual(
            a["root_contact_authority"],
            "LOWER_BODY_CONTACT_SOLVER",
        )

    def test_shared_boundary_clearance_adaptation_is_bounded(self) -> None:
        a=self.contract["authority"]
        v=self.contract["validation"]
        self.assertEqual(
            a["coordinated_boundary_clearance_adaptation"],
            "REUSE_ACCEPTED_MINIMAL_DEFORMED_MESH_SHOULDER_PROJECTION",
        )
        self.assertTrue(
            a["source_endpoint_projection_rule_preserved_outside_shared_boundary"]
        )
        self.assertEqual(
            v["coordinated_boundary_projection_only_frame"],
            61,
        )
        self.assertLessEqual(
            v[
                "coordinated_boundary_clearance_projection_max_shoulder_correction_deg"
            ],
            3.0,
        )
        self.assertLessEqual(
            v[
                "coordinated_boundary_nonshoulder_arm_local_matrix_error_max"
            ],
            1e-6,
        )

    def test_semantic_overlap_ceiling_is_zero(self) -> None:
        self.assertEqual(
            self.contract["validation"][
                "arm_lower_semantic_overlap_count_max"
            ],
            0,
        )

    def test_contact_and_boundary_gates_remain_strict(self) -> None:
        v=self.contract["validation"]
        self.assertLessEqual(
            v["shared_arm_boundary_local_matrix_error_max"],1e-6
        )
        self.assertLessEqual(
            v["shared_lower_boundary_local_matrix_error_max"],1e-6
        )
        self.assertLessEqual(v["root_horizontal_translation_max"],1e-5)
        self.assertTrue(v["post_overlay_contact_required"])
        self.assertTrue(v["sample_every_frame"])

    def test_scope_excludes_later_systems(self) -> None:
        p=self.contract["policy"]
        self.assertTrue(p["reverence_forbidden"])
        self.assertTrue(p["run_integration_forbidden"])
        self.assertTrue(p["music_sync_forbidden"])
        self.assertTrue(p["gameplay_changes_forbidden"])
        self.assertTrue(p["full_choreography_forbidden"])


if __name__=="__main__":
    unittest.main()
