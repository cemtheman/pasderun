from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RETARGET = ROOT / "scenes/characters/ballerina_motion_retarget_v2.gd"
WRAPPER = ROOT / "scenes/characters/ballerina_visual_v_1.tscn"
BOOTSTRAP = ROOT / "scenes/gameplay/dancer_visual_bootstrap.gd"
SOURCE_V5 = ROOT / "scenes/gameplay/dancer_visual_motion_v5.gd"


class Phase10BallerinaSemanticRetargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.retarget = RETARGET.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")
        cls.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        cls.source_v5 = SOURCE_V5.read_text(encoding="utf-8")

    def test_wrapper_uses_v2_semantic_retarget(self) -> None:
        self.assertIn(
            'res://scenes/characters/ballerina_motion_retarget_v2.gd',
            self.wrapper,
        )
        self.assertNotIn(
            'res://scenes/characters/ballerina_motion_retarget_v1.gd',
            self.wrapper,
        )

    def test_coordinate_contract_is_explicit(self) -> None:
        for contract in (
            "Dancer/gameplay travels along +X",
            "+Y is world up",
            "audience is on +Z",
            "visual front is local +Z",
        ):
            self.assertIn(contract, self.retarget)

    def test_all_choreography_states_are_semantically_retargeted(self) -> None:
        states = (
            "NEUTRAL",
            "STAGE_WALK",
            "STAGE_BOW",
            "STAGE_READY",
            "STAGE_FINAL_BOW",
            "TRAVEL",
            "JUMP",
            "AIRBORNE",
            "LANDING",
            "LOW_TRANSITION",
            "STUMBLE",
            "RECOVERY",
            "MUSIC_FLOW",
            "MUSIC_BUILD",
            "MUSIC_RELEASE",
            "MUSIC_PULSE",
            "MUSIC_CLIMAX",
            "MUSIC_PREP",
            "MUSIC_ACCENT",
        )
        block = re.search(
            r"const RETARGET_STATES := \{(.*?)\n\}",
            self.retarget,
            re.DOTALL,
        )
        self.assertIsNotNone(block)
        source = block.group(1)
        for state in states:
            self.assertIn(f'&"{state}": true', source)

    def test_balance_pose_is_intentionally_not_in_humanoid_library(self) -> None:
        block = re.search(
            r"const RETARGET_STATES := \{(.*?)\n\}",
            self.retarget,
            re.DOTALL,
        )
        self.assertIsNotNone(block)
        self.assertNotIn('&"BALANCE"', block.group(1))
        self.assertIn("BALANCE is intentionally absent", self.retarget)
        self.assertIn('&"BALANCE"', self.bootstrap)
        self.assertIn('_play_ballerina_animation(player, &"idle", true)', self.bootstrap)

    def test_root_orientation_uses_source_rig_relative_to_verified_model_base(self) -> None:
        self.assertIn(
            "_model_base_transform.basis * source_root_basis",
            self.retarget,
        )
        self.assertNotIn("_face_active_camera", self.retarget)
        self.assertNotIn("look_at(", self.retarget)

    def test_joint_retarget_uses_frame_conjugation_not_euler_axis_copy(self) -> None:
        required = (
            "source_rig_world_inverse",
            "source_pose_in_rig",
            "rig_frame",
            "* source_pose_in_rig",
            "* rig_frame_inverse",
            "common_world",
            "* oriented_delta_in_gameplay",
            "* common_world_inverse",
            "delta_world * baseline_world_basis",
            "skeleton_world_inverse * desired_world_basis",
        )
        for token in required:
            self.assertIn(token, self.retarget)

        forbidden = (
            "get_euler()",
            "rotation.x =",
            "rotation.y =",
            "rotation.z =",
            "STAGE_AUDIENCE_RIGHT_YAW",
        )
        for token in forbidden:
            self.assertNotIn(token, self.retarget)

    def test_target_proportions_and_joint_origins_are_preserved(self) -> None:
        self.assertIn(
            "Transform3D(desired_skeleton_basis, current_global.origin)",
            self.retarget,
        )
        self.assertNotIn("set_bone_pose_position", self.retarget)
        self.assertNotIn("set_bone_rest", self.retarget)

    def test_source_root_motion_is_scaled_from_body_proportions(self) -> None:
        self.assertIn("_compute_motion_scale()", self.retarget)
        self.assertIn("_source_rig.position * _motion_scale", self.retarget)
        self.assertIn("target_span / source_span", self.retarget)

    def test_reverence_uses_tpose_port_de_bras_and_long_trunk(self) -> None:
        self.assertIn('&"_T-Pose"', self.retarget)
        self.assertIn("_apply_classical_reverence_upper_body", self.retarget)
        self.assertIn('_reset_global_basis_to_idle("Torso")', self.retarget)
        self.assertIn('_reset_global_basis_to_idle("Head")', self.retarget)
        self.assertIn("_downward_rotation_about_visual_front", self.retarget)

    def test_low_transition_keeps_phase7_v5_foot_preserving_contract(self) -> None:
        for token in (
            "_low_front_support_pose_v5",
            "_low_back_brush_pose_v5",
            "_low_back_support_pose_v5",
            "_low_front_brush_pose_v5",
            "pelvis can descend without shortening",
        ):
            self.assertIn(token, self.source_v5)
        self.assertIn('&"LOW_TRANSITION": true', self.retarget)

    def test_bootstrap_yields_choreography_states_to_retarget_layer(self) -> None:
        self.assertIn("handles_visual_state", self.bootstrap)
        self.assertIn("player.stop()", self.bootstrap)
        self.assertIn(
            'Callable(self, "_on_ballerina_visual_state_changed").bind(external_visual, player)',
            self.bootstrap,
        )


if __name__ == "__main__":
    unittest.main()
