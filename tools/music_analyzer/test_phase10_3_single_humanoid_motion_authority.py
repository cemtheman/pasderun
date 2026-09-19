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
        self.assertIn("STUMBLE_TORSO_PITCH := deg_to_rad(32.0)", self.controller)
        self.assertIn("STUMBLE_DURATION := 0.36", self.controller)
        self.assertIn("RECOVERY_DURATION := 0.72", self.controller)

        stumble = re.search(
            r'func _apply_stumble_overlay\(\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        recovery = re.search(
            r'func _apply_recovery_overlay\(\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(stumble)
        self.assertIsNotNone(recovery)
        self.assertIn("var foot_catch := smoothstep(0.0, 0.24, t)", stumble.group(0))
        self.assertIn("sin(STUMBLE_TORSO_PITCH)", stumble.group(0))
        self.assertIn("same_side_as_catch", stumble.group(0))
        self.assertIn("var catch_left := not _trip_uses_left_foot", recovery.group(0))
        self.assertIn("var catch_foot_target := Vector3(", recovery.group(0))
        self.assertIn("var catch_knee_target :=", recovery.group(0))
        self.assertIn("_steer_segment_toward_world_point(", recovery.group(0))
        self.assertIn("var floor_y := minf(", recovery.group(0))
        self.assertNotIn("_animation_player.seek", stumble.group(0))
        self.assertNotIn("_animation_player.seek", recovery.group(0))
        self.assertNotIn("_animation_player.pause", stumble.group(0))
        self.assertNotIn("_animation_player.pause", recovery.group(0))



    def test_reverence_uses_current_humanoid_geometry_not_local_euler_guesses(self) -> None:
        for token in (
            'const OPENING_REVERENCE := &"OPENING_REVERENCE"',
            'const FINAL_REVERENCE := &"FINAL_REVERENCE"',
            "func _reverence_profile",
            "func _apply_reverence_phrase",
            "func _apply_reverence_leg_chain",
            "func _apply_reverence_clavicle_support",
            "func _apply_reverence_port_de_bras",
            "func _apply_reverence_epaulement",
            "func _steer_segment_toward_world_point",
            "Quaternion(current_direction_world, desired)",
            'var knee_angle := float(profile["plie_angle"]) * depth',
            "var derived_drop := leg_length * (1.0 - cos(knee_angle))",
            "var left_foot_target := _bone_world_position(left_foot)",
            "var knee_target := hip_position.lerp(floor_target, 0.52)",
            "var toe_target := floor_target + toe_direction * toe_length",
            "var shoulder_center := chest_position",
            "var classical_hand_floor := shoulder_center.y - reach * 0.30",
            "hand_target.y = maxf(hand_target.y, classical_hand_floor)",
        ):
            self.assertIn(token, self.controller)
        self.assertIn('"plie_angle": 0.50', self.controller)
        self.assertIn('"plie_angle": 0.62', self.controller)
        self.assertIn(
            "0.045 * placement + 0.145 * depth + 0.075 * turnout",
            self.controller,
        )
        self.assertNotIn("Vector3(side * (turnout - cross_bias), -c, s)", self.controller)
        self.assertNotIn("_rx(", self.controller)
        self.assertNotIn("_ry(", self.controller)
        self.assertNotIn("_rz(", self.controller)
        self.assertNotIn("kneel", self.controller.lower())
        self.assertNotIn("hands_on_hips", self.controller.lower())
    def test_phase1031_reverence_profiles_have_distinct_phrasing_and_synced_callers(self) -> None:
        for token in (
            '"place_end": 0.55',
            '"plie_end": 1.35',
            '"rise_end": 1.95',
            '"settle_end": 2.25',
            '"place_end": 0.60',
            '"plie_end": 1.55',
            '"rise_end": 2.35',
            '"settle_end": 2.85',
            "_apply_reverence_phrase(_state_elapsed, OPENING_REVERENCE)",
            "_apply_reverence_phrase(_state_elapsed, FINAL_REVERENCE)",
        ):
            self.assertIn(token, self.controller)
        self.assertIn("@export var bow_duration := 2.25", self.start_gate)
        self.assertIn(
            "const COMPLETION_FINAL_BOW_DURATION := 2.85",
            self.recovery,
        )



    def test_prefixed_import_bones_have_safe_suffix_resolution(self) -> None:
        finder = re.search(
            r'func _find_bone\(.*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(finder)
        self.assertIn("if normalized in normalized_aliases:", finder.group(0))
        self.assertIn("alias.length() >= 6", finder.group(0))
        self.assertIn("normalized.ends_with(alias)", finder.group(0))



    def test_runtime_initialization_is_error_free_for_empty_animation_and_busy_parent(self) -> None:
        capture = re.search(
            r'func _capture_idle_baseline\(\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        helpers = re.search(
            r'func _attach_presentation_helpers\(\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(capture)
        self.assertIsNotNone(helpers)
        self.assertIn('var previous_position := 0.0', capture.group(0))
        self.assertIn('if previous_animation != &"":', capture.group(0))
        self.assertIn(
            'previous_position = _animation_player.current_animation_position',
            capture.group(0),
        )
        self.assertIn(
            '_dancer.call_deferred("add_child", tap_feedback)',
            helpers.group(0),
        )
        self.assertNotIn('_dancer.add_child(tap_feedback)', helpers.group(0))

    def test_unresolved_hand_uses_forearm_topology_fallback(self) -> None:
        resolver = re.search(
            r'func _resolve_humanoid_bones\(\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        infer = re.search(
            r'func _infer_distal_joint_from_chain\([^)]*\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(resolver)
        self.assertIsNotNone(infer)
        self.assertIn('if int(_bones["left_hand"]) < 0:', resolver.group(0))
        self.assertIn('if int(_bones["right_hand"]) < 0:', resolver.group(0))
        self.assertIn('_infer_distal_joint_from_chain(', resolver.group(0))
        self.assertIn('_skeleton.get_bone_parent(bone_idx) == current', infer.group(0))
        self.assertIn('if child_count != 1:', infer.group(0))
        self.assertIn('return current if current != start_idx else -1', infer.group(0))



    def test_phase1032_uses_audited_ballet_rig_articulation(self) -> None:
        resolver = re.search(
            r'func _resolve_humanoid_bones\(\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        clavicle = re.search(
            r'func _apply_reverence_clavicle_support\([^)]*\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        port = re.search(
            r'func _apply_reverence_port_de_bras\([^)]*\).*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(resolver)
        self.assertIsNotNone(clavicle)
        self.assertIsNotNone(port)

        for token in (
            '"left_clavicle": _find_bone(["leftclavicle", "claviclel", "shoulderl"])',
            '"right_clavicle": _find_bone(["rightclavicle", "clavicler", "shoulderr"])',
            '"left_middle": _find_bone(["leftmiddle", "middlel", "middlefingerl"])',
            '"right_middle": _find_bone(["rightmiddle", "middler", "middlefingerr"])',
            '"lefttoes", "toesl"',
            '"righttoes", "toesr"',
        ):
            self.assertIn(token, resolver.group(0))

        self.assertIn('var strength := (0.18 if final_variant else 0.15)', clavicle.group(0))
        self.assertIn('_steer_segment_toward_world_point(', clavicle.group(0))
        self.assertIn('var middle := _bone_index(', port.group(0))
        self.assertIn('var hand_finish_direction :=', port.group(0))
        self.assertIn('var hand_finish_target :=', port.group(0))
        self.assertIn('-outward * (0.74 if expressive else 0.66)', port.group(0))
        self.assertIn('audience_forward * 0.28', port.group(0))
        self.assertIn('clampf(hand_finish_strength, 0.16, 0.42)', port.group(0))
        self.assertIn('outward * upper_length * 0.68', port.group(0))
        self.assertIn('outward * upper_length * 0.50', port.group(0))
        self.assertIn('_steer_segment_toward_world_point(', port.group(0))


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
