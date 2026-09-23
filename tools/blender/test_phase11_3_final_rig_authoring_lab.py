#!/usr/bin/env python3

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTRACT_PATH = ROOT / "data/choreography/stumble_recovery_final_rig_v1.authoring_contract.json"
BUILDER_PATH = ROOT / "tools/blender/build_stumble_recovery_final_rig_lab_v1.py"
RUNNER_PATH = ROOT / "tools/blender/run_phase11_3_final_rig_authoring_lab.ps1"

CONTRACT = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
BUILDER = BUILDER_PATH.read_text(encoding="utf-8")
RUNNER = RUNNER_PATH.read_text(encoding="utf-8")


class Phase113FinalRigAuthoringLabTests(unittest.TestCase):
    def test_contract_uses_final_game_rig_as_authority(self) -> None:
        self.assertEqual(CONTRACT["phase"], "11.3")
        self.assertEqual(CONTRACT["target"]["expected_armature"], "Rig")
        self.assertEqual(
            CONTRACT["target"]["authority"],
            "final_game_rig",
        )
        self.assertEqual(
            CONTRACT["target"]["action"],
            "stumble_recovery_v1",
        )

    def test_source_is_visual_reference_only(self) -> None:
        self.assertEqual(
            CONTRACT["source_reference"]["role"],
            "visual_reference_only",
        )
        policy = CONTRACT["authoring_policy"]
        self.assertFalse(policy["automated_source_to_target_retarget"])
        self.assertFalse(policy["source_reference_may_drive_target_bones"])
        self.assertFalse(
            policy["source_reference_may_create_target_constraints"]
        )

    def test_nine_key_pose_gate_is_locked(self) -> None:
        labels = CONTRACT["source_reference"]["labels"]
        self.assertEqual(len(labels), 9)
        self.assertEqual(labels[0], "RUN")
        self.assertEqual(labels[-1], "STABLE RUN")
        self.assertEqual(
            CONTRACT["authoring_policy"]["key_pose_count"],
            9,
        )

    def test_builder_creates_no_retarget_mapping(self) -> None:
        self.assertNotIn("source_to_target", BUILDER)
        self.assertNotIn("COPY_ROTATION", BUILDER)
        self.assertNotIn("COPY_TRANSFORMS", BUILDER)
        self.assertIn(
            '"source_visual_reference"',
            BUILDER,
        )
        self.assertIn(
            '"final_game_rig_authority"',
            BUILDER,
        )

    def test_target_action_is_created_directly(self) -> None:
        self.assertIn(
            'ACTION_NAME = "stumble_recovery_v1"',
            BUILDER,
        )
        self.assertIn(
            "target_armature.animation_data.action = target_action",
            BUILDER,
        )

    def test_runner_is_fail_fast_and_stale_output_safe(self) -> None:
        self.assertIn("--python-exit-code 1", RUNNER)
        self.assertIn("Remove-Item -Force", RUNNER)
        self.assertIn(
            "FINAL-RIG AUTHORING LAB PASS",
            RUNNER,
        )


if __name__ == "__main__":
    unittest.main()
