from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "project.godot"
CONTROLLER_PATH = ROOT / "scenes/characters/humanoid_motion_controller.gd"
BALLERINA_PATH = ROOT / "scenes/characters/ballerina_visual_v_1.tscn"
DANCER_PATH = ROOT / "scenes/gameplay/dancer.gd"
START_GATE_PATH = ROOT / "scenes/gameplay/runtime_start_gate.gd"
RECOVERY_PATH = ROOT / "scenes/gameplay/run_recovery_manager.gd"
CHOREO_PATH = ROOT / "scenes/gameplay/music_choreography_director.gd"
TAP_PATH = ROOT / "scenes/gameplay/dancer_tap_feedback.gd"


class Phase103SingleHumanoidMotionAuthorityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project = PROJECT.read_text(encoding="utf-8")
        cls.controller = CONTROLLER_PATH.read_text(encoding="utf-8")
        cls.ballerina = BALLERINA_PATH.read_text(encoding="utf-8")
        cls.dancer = DANCER_PATH.read_text(encoding="utf-8")
        cls.start_gate = START_GATE_PATH.read_text(encoding="utf-8")
        cls.recovery = RECOVERY_PATH.read_text(encoding="utf-8")
        cls.choreo = CHOREO_PATH.read_text(encoding="utf-8")
        cls.tap = TAP_PATH.read_text(encoding="utf-8")

    def test_exactly_one_active_humanoid_motion_authority(self) -> None:
        self.assertTrue(CONTROLLER_PATH.exists())
        self.assertIn(
            'path="res://scenes/characters/humanoid_motion_controller.gd"',
            self.ballerina,
        )
        for dead_path in (
            ROOT / "scenes/gameplay/dancer_visual.gd",
            ROOT / "scenes/gameplay/dancer_visual_bootstrap.gd",
            ROOT / "scenes/gameplay/dancer_visual_motion_v2.gd",
            ROOT / "scenes/gameplay/dancer_visual_motion_v3.gd",
            ROOT / "scenes/gameplay/dancer_visual_motion_v4.gd",
            ROOT / "scenes/gameplay/dancer_visual_motion_v5.gd",
            ROOT / "scenes/characters/ballerina_motion_retarget_v1.gd",
            ROOT / "scenes/characters/ballerina_motion_retarget_v2.gd",
        ):
            self.assertFalse(dead_path.exists(), dead_path)

        active_sources = "\n".join(
            (
                self.project,
                self.controller,
                self.ballerina,
                self.start_gate,
                self.recovery,
                self.choreo,
                self.tap,
            )
        )
        for token in (
            "DancerVisual",
            "dancer_visual_motion",
            "ballerina_motion_retarget",
            "_source_visual",
            "_source_rig",
            "semantic mannequin",
        ):
            self.assertNotIn(token, active_sources)

    def test_native_clips_are_the_base_motion(self) -> None:
        for clip in (
            '&"idle"',
            '&"walk"',
            '&"run"',
            '&"jump_start"',
            '&"jump_falling"',
        ):
            self.assertIn(clip, self.controller)
        self.assertNotIn("AnimationTree", self.controller)
        self.assertIn('STATE_LANDING', self.controller)
        self.assertIn('_begin_landing_run_contact()', self.controller)

    def test_gait_is_world_speed_calibrated_from_real_foot_trajectories(self) -> None:
        for token in (
            "GAIT_SAMPLE_COUNT := 32",
            "_measure_backward_support_speed",
            "_bone_world_position(left_foot)",
            "desired_speed / backward_speed",
            "_sync_native_gait_speed",
        ):
            self.assertIn(token, self.controller)
        landing = re.search(
            r'func _begin_landing_run_contact\(\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(landing)
        self.assertIn('_animation_player.play(&"run", 0.08)', landing.group(0))
        self.assertIn('_animation_player.seek(', landing.group(0))
        self.assertNotIn('_animation_player.pause()', landing.group(0))

    def test_landing_precedes_high_drop_stumble_and_continues_opposite_step(self) -> None:
        resolver = re.search(
            r'func _resolve_visual_state\(.*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(resolver)
        source = resolver.group(0)
        self.assertLess(
            source.index("return STATE_LANDING"),
            source.index("if locomotion == STATE_STUMBLE:"),
        )
        self.assertIn("_landing_support_left", self.controller)
        self.assertIn("_capture_trip_side_from_current_gait", self.controller)
        self.assertIn("var catch_left := not _trip_uses_left_foot", self.controller)

    def test_stumble_is_readable_human_reaction(self) -> None:
        self.assertIn("STUMBLE_TORSO_PITCH := deg_to_rad(30.0)", self.controller)
        self.assertIn("STUMBLE_DURATION := 0.36", self.controller)
        self.assertIn("RECOVERY_DURATION := 0.72", self.controller)
        self.assertIn("var catch_left := not _trip_uses_left_foot", self.controller)
        stumble = re.search(
            r'func _apply_stumble_overlay\(\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(stumble)
        self.assertIn("sin(STUMBLE_TORSO_PITCH)", stumble.group(0))
        self.assertIn("Vector3(-0.14, 0.990, 0.0)", stumble.group(0))

    def test_reverence_uses_current_humanoid_geometry_not_local_euler_guesses(self) -> None:
        for token in (
            "Quaternion(current_direction_world, desired)",
            "_audience_pair_side_sign",
            "Vector3(side * upper_out, upper_y, upper_z)",
            "Vector3(-side * fore_in, fore_y, fore_z)",
            "derived_drop := leg_length * (1.0 - cos(knee_angle))",
            "Vector3(side * turnout, -c, s)",
            "Vector3(-side * turnout * 0.55, -c, -s)",
        ):
            self.assertIn(token, self.controller)
        self.assertNotIn("_rx(", self.controller)
        self.assertNotIn("_ry(", self.controller)
        self.assertNotIn("_rz(", self.controller)
        self.assertNotIn("kneel", self.controller.lower())

    def test_stage_and_music_callers_target_ballerina_directly(self) -> None:
        for source in (self.start_gate, self.recovery, self.choreo, self.tap):
            self.assertIn("BallerinaVisualV1", source)
            self.assertNotIn("DancerVisual", source)

    def test_music_end_sequence_is_decelerate_walk_bow_turn_walk_exit(self) -> None:
        for phase in (
            "DECELERATE_TO_WALK",
            "WALK_TO_MARK",
            "FINAL_BOW",
            "EXIT_TURN",
            "EXIT_WALK",
        ):
            self.assertIn(phase, self.recovery)
        self.assertIn("COMPLETION_DECEL_DURATION := 0.90", self.recovery)
        self.assertIn("audio_player.finished.connect(_on_music_finished)", self.recovery)

        run = self.recovery.index('_set_completion_stage_visual(&"RUN")')
        walk_1 = self.recovery.index('_set_completion_stage_visual(&"WALK")')
        bow = self.recovery.index('_set_completion_stage_visual(&"FINAL_BOW")')
        exit_turn = self.recovery.index('_set_completion_stage_visual(&"EXIT_TURN")')
        walk_2 = self.recovery.index(
            '_set_completion_stage_visual(&"WALK")',
            walk_1 + 1,
        )
        self.assertLess(run, walk_1)
        self.assertLess(walk_1, bow)
        self.assertLess(bow, exit_turn)
        self.assertLess(exit_turn, walk_2)

    def test_dancer_remains_physics_authority(self) -> None:
        for token in (
            "move_and_slide()",
            "velocity.x = stage_entrance_speed",
            "func begin_stage_ending(speed: float = 0.0) -> void:",
            "func set_stage_ending_speed(speed: float) -> void:",
        ):
            self.assertIn(token, self.dancer)
        for forbidden in (
            "move_and_slide()",
            "move_and_collide(",
            "_dancer.global_position =",
            "_dancer.velocity =",
        ):
            self.assertNotIn(forbidden, self.controller)


if __name__ == "__main__":
    unittest.main()
