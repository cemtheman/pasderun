#!/usr/bin/env python3

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILDER = (
    ROOT / "tools/blender/author_stumble_keyposes_a_v1.py"
).read_text(encoding="utf-8")
RUNNER = (
    ROOT / "tools/blender/run_phase11_3_final_rig_keyposes_a.ps1"
).read_text(encoding="utf-8")


class Phase113FinalRigKeyposesATests(unittest.TestCase):
    def test_pass_is_directly_authored_on_final_rig(self) -> None:
        self.assertIn('ACTION_NAME = "stumble_recovery_v1"', BUILDER)
        self.assertIn('"final_rig_direct_keyposes_a"', BUILDER)
        self.assertIn('"source_transform_sampling": False', BUILDER)

    def test_only_first_three_semantic_poses_are_authored(self) -> None:
        self.assertIn(
            'POSE_NAMES = ("RUN", "TOE CATCH", "MOMENTUM FORWARD")',
            BUILDER,
        )
        self.assertNotIn('"PEAK STUMBLE": {', BUILDER)

    def test_source_pose_is_not_sampled_for_target_transforms(self) -> None:
        self.assertNotIn('source.pose.bones', BUILDER)
        self.assertNotIn('Runner_RIGAction', BUILDER)
        self.assertNotIn('source_to_target', BUILDER)
        self.assertNotIn('COPY_ROTATION', BUILDER)
        self.assertNotIn('COPY_TRANSFORMS', BUILDER)

    def test_keyposes_use_joint_landmarks_not_straight_segment_vectors(self) -> None:
        self.assertIn("def authored_point(", BUILDER)
        self.assertIn("def apply_landmark_chain(", BUILDER)
        self.assertIn('("elbow", "wrist", "finish")', BUILDER)
        self.assertIn('("knee", "ankle", "finish")', BUILDER)
        self.assertNotIn("def apply_segment_chain(", BUILDER)
        self.assertIn('"TOE CATCH": {', BUILDER)
        self.assertIn('"MOMENTUM FORWARD": {', BUILDER)

    def test_pose_uses_final_rig_calibration_and_lengths(self) -> None:
        self.assertIn(
            'ballet_rig_calibration_seed_v1.json',
            BUILDER,
        )
        self.assertIn('core.joint_length(', BUILDER)
        self.assertIn('core.set_roll_stable_bone_frame(', BUILDER)

    def test_preview_stops_at_momentum_gate(self) -> None:
        self.assertIn(
            'marker_frames["MOMENTUM FORWARD"]',
            BUILDER,
        )
        self.assertIn(
            '"human_visual_review_before_peak_stumble"',
            BUILDER,
        )

    def test_runner_is_fail_fast(self) -> None:
        self.assertIn("--python-exit-code 1", RUNNER)
        self.assertIn("Remove-Item -Force", RUNNER)
        self.assertIn("FINAL-RIG KEYPOSES A PASS", RUNNER)


if __name__ == "__main__":
    unittest.main()
