from __future__ import annotations

import math
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RETARGET = ROOT / "scenes/characters/ballerina_motion_retarget_v2.gd"
WRAPPER = ROOT / "scenes/characters/ballerina_visual_v_1.tscn"
BOOTSTRAP = ROOT / "scenes/gameplay/dancer_visual_bootstrap.gd"
SOURCE_V4 = ROOT / "scenes/gameplay/dancer_visual_motion_v4.gd"
SOURCE_V5 = ROOT / "scenes/gameplay/dancer_visual_motion_v5.gd"
VISUAL = ROOT / "scenes/gameplay/dancer_visual.gd"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
START_GATE = ROOT / "scenes/gameplay/runtime_start_gate.gd"
RECOVERY_MANAGER = ROOT / "scenes/gameplay/run_recovery_manager.gd"
COURSE = ROOT / "scenes/gameplay/generated/continuous_technical_course.tscn"
FULL_BRIDGE = ROOT / "scenes/gameplay/generated/graceful_opening_00_140_bridge.tscn"
FULL_RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"
BALLERINA_TEST_SCENE = ROOT / "scenes/gameplay/graceful_opening_ballerina_test.tscn"


class Phase10BallerinaSemanticRetargetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.retarget = RETARGET.read_text(encoding="utf-8")
        cls.wrapper = WRAPPER.read_text(encoding="utf-8")
        cls.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        cls.source_v4 = SOURCE_V4.read_text(encoding="utf-8")
        cls.source_v5 = SOURCE_V5.read_text(encoding="utf-8")
        cls.visual = VISUAL.read_text(encoding="utf-8")
        cls.dancer = DANCER.read_text(encoding="utf-8")
        cls.start_gate = START_GATE.read_text(encoding="utf-8")
        cls.recovery_manager = RECOVERY_MANAGER.read_text(encoding="utf-8")
        cls.course = COURSE.read_text(encoding="utf-8")
        cls.full_bridge = FULL_BRIDGE.read_text(encoding="utf-8")
        cls.full_runtime = FULL_RUNTIME.read_text(encoding="utf-8")
        cls.ballerina_test_scene = BALLERINA_TEST_SCENE.read_text(encoding="utf-8")


    @staticmethod
    def _matmul(a, b):
        if isinstance(b[0], (int, float)):
            return [
                sum(a[row][k] * b[k] for k in range(3))
                for row in range(3)
            ]
        return [
            [
                sum(a[row][k] * b[k][col] for k in range(3))
                for col in range(3)
            ]
            for row in range(3)
        ]

    @staticmethod
    def _transpose(m):
        return [[m[col][row] for col in range(3)] for row in range(3)]

    @staticmethod
    def _rx(angle):
        c, s = math.cos(angle), math.sin(angle)
        return [[1.0, 0.0, 0.0], [0.0, c, -s], [0.0, s, c]]

    @staticmethod
    def _ry(angle):
        c, s = math.cos(angle), math.sin(angle)
        return [[c, 0.0, s], [0.0, 1.0, 0.0], [-s, 0.0, c]]

    @staticmethod
    def _rz(angle):
        c, s = math.cos(angle), math.sin(angle)
        return [[c, -s, 0.0], [s, c, 0.0], [0.0, 0.0, 1.0]]

    def test_coordinate_math_preserves_travel_and_stage_facing(self) -> None:
        base = self._ry(math.pi * 0.5)
        stage_turn = self._ry(-math.pi * 0.5)
        visual_front = [0.0, 0.0, 1.0]

        travel_front = self._matmul(base, visual_front)
        stage_front = self._matmul(self._matmul(base, stage_turn), visual_front)

        self.assertAlmostEqual(travel_front[0], 1.0, places=6)
        self.assertAlmostEqual(travel_front[2], 0.0, places=6)
        self.assertAlmostEqual(stage_front[0], 0.0, places=6)
        self.assertAlmostEqual(stage_front[2], 1.0, places=6)

    def test_stage_conjugation_turns_side_view_bow_toward_audience(self) -> None:
        stage_turn = self._ry(-math.pi * 0.5)
        side_view_bow = self._rz(-0.34)
        oriented = self._matmul(
            self._matmul(stage_turn, side_view_bow),
            self._transpose(stage_turn),
        )
        up = [0.0, 1.0, 0.0]
        bowed_up = self._matmul(oriented, up)

        # The original negative Z hinge is no longer a sideways roll: after the
        # 90 degree stage turn it inclines the trunk toward +Z, the audience.
        self.assertGreater(bowed_up[2], 0.0)
        self.assertGreater(bowed_up[1], 0.0)

    def test_stage_conjugation_turns_source_arm_hinge_into_front_port_de_bras(self) -> None:
        stage_turn = self._ry(-math.pi * 0.5)
        source_arm = self._rx(0.40)
        oriented = self._matmul(
            self._matmul(stage_turn, source_arm),
            self._transpose(stage_turn),
        )
        down = [0.0, -1.0, 0.0]
        opened = self._matmul(oriented, down)

        # One arm opens along +X; the mirrored source arm opens along -X.
        self.assertGreater(opened[0], 0.0)
        self.assertLess(opened[1], 0.0)

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

    def test_native_humanoid_clips_own_dynamic_locomotion(self) -> None:
        block = re.search(
            r"const RETARGET_STATES := \{(.*?)\n\}",
            self.retarget,
            re.DOTALL,
        )
        self.assertIsNotNone(block)
        source = block.group(1)

        for state in (
            "STAGE_BOW",
            "STAGE_READY",
            "STAGE_FINAL_BOW",
            "STAGE_EXIT_TURN",
        ):
            self.assertIn(f'&"{state}": true', source)

        for state in (
            "NEUTRAL",
            "STAGE_WALK",
            "TRAVEL",
            "JUMP",
            "AIRBORNE",
            "LANDING",
            "LOW_TRANSITION",
            "BALANCE",
            "STUMBLE",
            "RECOVERY",
            "MUSIC_FLOW",
            "MUSIC_BUILD",
            "MUSIC_RELEASE",
            "MUSIC_PULSE",
            "MUSIC_CLIMAX",
            "MUSIC_PREP",
            "MUSIC_ACCENT",
        ):
            self.assertNotIn(f'&"{state}": true', source)

        for state in ("JUMP", "AIRBORNE", "LANDING", "STUMBLE", "RECOVERY"):
            self.assertIn(f'&"{state}": true', self.retarget)
        self.assertIn("const OVERLAY_STATES := {", self.retarget)
        self.assertIn("_apply_running_trip_overlay(state)", self.retarget)

        self.assertIn(
            '_play_ballerina_animation(player, &"walk", true, 1.0)',
            self.bootstrap,
        )
        self.assertIn(
            '_play_ballerina_animation(player, &"run", true, 1.0)',
            self.bootstrap,
        )
        self.assertIn(
            '_play_ballerina_animation(player, &"jump_start", false, 1.0)',
            self.bootstrap,
        )
        self.assertIn(
            '_play_ballerina_animation(player, &"jump_falling", true, 1.0)',
            self.bootstrap,
        )
        self.assertIn("_hold_landing_contact(player)", self.bootstrap)
        self.assertIn("_play_run_from_pending_contact(player, 1.0)", self.bootstrap)
        self.assertIn("RUN_CONTACT_SAMPLE_COUNT := 32", self.bootstrap)
        self.assertIn("_pending_run_contact_phase", self.bootstrap)
        self.assertIn("_landing_support_left", self.bootstrap)


    def test_balance_zone_preserves_always_run_visual_contract(self) -> None:
        block = re.search(
            r"const RETARGET_STATES := \{(.*?)\n\}",
            self.retarget,
            re.DOTALL,
        )
        self.assertIsNotNone(block)
        self.assertNotIn('&"BALANCE": true', block.group(1))
        self.assertIn("func _balance_animation() -> Animation:", self.source_v5)
        balance_override = re.search(
            r"func _balance_animation\(\) -> Animation:(.*?)(?=\n\n|\Z)",
            self.source_v5,
            re.DOTALL,
        )
        self.assertIsNotNone(balance_override)
        self.assertIn("return _travel_animation()", balance_override.group(1))
        self.assertIn("velocity.x = run_speed * _locomotion_speed_multiplier()", self.dancer)
        self.assertIn("velocity.z = (", self.dancer)
        self.assertIn("balance_drift_direction", self.dancer)

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

    def test_reverence_uses_anatomical_front_plie_and_rounded_port_de_bras(self) -> None:
        self.assertIn("_apply_classical_reverence_upper_body", self.retarget)
        self.assertIn("var knee_angle := 0.52 * depth", self.retarget)
        self.assertIn(
            'Vector3(-outward, -c, s).normalized()',
            self.retarget,
        )
        self.assertIn(
            'Vector3(outward, -c, s).normalized()',
            self.retarget,
        )
        self.assertIn(
            'Vector3(-outward * 0.45, -c, -s).normalized()',
            self.retarget,
        )
        self.assertIn("_opening_leg_vertical_shortening(knee_angle)", self.retarget)
        self.assertIn(
            "Vector3(-0.62, -0.64, 0.34).lerp(",
            self.retarget,
        )
        self.assertIn(
            "Vector3(-0.92, -0.22, 0.28)",
            self.retarget,
        )
        self.assertIn(
            'Vector3(0.0, 0.999, 0.035 * depth).normalized()',
            self.retarget,
        )

    def test_low_transition_keeps_phase7_v5_contract_without_full_body_retarget(self) -> None:
        for token in (
            "_low_front_support_pose_v5",
            "_low_back_brush_pose_v5",
            "_low_back_support_pose_v5",
            "_low_front_brush_pose_v5",
            "pelvis can descend without shortening",
        ):
            self.assertIn(token, self.source_v5)

        retarget_block = re.search(
            r"const RETARGET_STATES := \{(.*?)\n\}",
            self.retarget,
            re.DOTALL,
        )
        self.assertIsNotNone(retarget_block)
        self.assertNotIn('&"LOW_TRANSITION": true', retarget_block.group(1))
        self.assertIn(
            '_play_ballerina_animation(player, &"run", true, 0.92)',
            self.bootstrap,
        )

    def test_opening_reverence_is_humanoid_authored_after_audience_turn(self) -> None:
        self.assertIn(
            'if state == &"STAGE_BOW" or state == &"STAGE_READY":',
            self.retarget,
        )
        self.assertIn(
            "no mannequin limb\n\t\t# articulation is transferred during BOW/READY",
            self.retarget,
        )
        self.assertIn(
            "(_state_elapsed - STAGE_BOW_TURN_TIME)",
            self.retarget,
        )
        self.assertIn(
            "/ maxf(STAGE_BOW_DURATION - STAGE_BOW_TURN_TIME, 0.001)",
            self.retarget,
        )
        self.assertIn(
            "_apply_classical_reverence_upper_body(phase, false)",
            self.retarget,
        )

    def test_jump_landing_plants_contact_then_resumes_on_opposite_foot(self) -> None:
        self.assertIn("func _hold_landing_contact", self.bootstrap)
        self.assertIn("func _play_run_from_pending_contact", self.bootstrap)
        self.assertIn("func _cache_run_contact_phases", self.bootstrap)
        self.assertIn(
            "var landing_left := left_y <= right_y",
            self.bootstrap,
        )
        self.assertIn(
            "var next_phase := right_phase if landing_left else left_phase",
            self.bootstrap,
        )
        self.assertIn(
            'player.set_meta("_pending_run_contact_phase", next_phase)',
            self.bootstrap,
        )
        self.assertIn("player.pause()", self.bootstrap)
        self.assertIn(
            'player.play(&"run", 0.12)',
            self.bootstrap,
        )
        self.assertIn(
            'player.seek(',
            self.bootstrap,
        )
        landing_branch = re.search(
            r'&"LANDING":(.*?)(?=\n\t\t&"|\n\t\t_:)',
            self.bootstrap,
            re.DOTALL,
        )
        self.assertIsNotNone(landing_branch)
        self.assertIn("_hold_landing_contact(player)", landing_branch.group(1))


    def test_landing_absorption_uses_actual_support_and_drop_context(self) -> None:
        self.assertIn("get_last_landing_drop_distance", self.dancer)
        self.assertIn("get_last_landing_was_jump", self.dancer)
        self.assertIn(
            '_animation_player.get_meta("_landing_support_left", false)',
            self.retarget,
        )
        self.assertIn(
            'var support_hip := "LegBackHip" if support_left else "LegFrontHip"',
            self.retarget,
        )
        self.assertIn(
            "var impact := 0.58 if was_jump else clampf(",
            self.retarget,
        )
        self.assertIn(
            "var compression_curve := sin(PI * clampf(t / 0.92, 0.0, 1.0))",
            self.retarget,
        )
        self.assertIn(
            "Vector3(0.26, -0.964, side).normalized()",
            self.retarget,
        )
        self.assertIn(
            "Vector3(-0.18, -0.983, side * 0.45).normalized()",
            self.retarget,
        )

    def test_trip_uses_actual_lead_foot_and_opposite_leg_for_recovery(self) -> None:
        self.assertIn("func _capture_trip_side_from_current_run", self.retarget)
        self.assertIn(
            "_trip_uses_left_foot = left_world.x > right_world.x",
            self.retarget,
        )
        self.assertIn(
            'var trip_hip := "LegBackHip" if _trip_uses_left_foot else "LegFrontHip"',
            self.retarget,
        )
        self.assertIn(
            'var catch_hip := "LegFrontHip" if _trip_uses_left_foot else "LegBackHip"',
            self.retarget,
        )
        self.assertIn(
            "if state == &\"STUMBLE\":\n\t\t\t_capture_trip_side_from_current_run()",
            self.retarget,
        )

    def test_high_fall_does_not_double_apply_visual_gravity(self) -> None:
        stumble = re.search(
            r'if state == &"STUMBLE":(.*?)(?=\n\tif state != &"RECOVERY":)',
            self.retarget,
            re.DOTALL,
        )
        self.assertIsNotNone(stumble)
        self.assertIn("-0.050 * impact", stumble.group(1))
        self.assertIn("\n\t\t\t0.0,\n\t\t\t0.0\n\t\t)", stumble.group(1))
        self.assertNotIn("9.81", stumble.group(1))

        recovery = re.search(
            r'if state != &"RECOVERY":.*?(var t :=.*?)(?=\n\nfunc _steer_current_chain_world_direction)',
            self.retarget,
            re.DOTALL,
        )
        self.assertIsNotNone(recovery)
        self.assertIn("-0.050 * (1.0 - release)", recovery.group(1))
        self.assertNotIn("rebound", recovery.group(1))

    def test_airborne_and_landing_contact_precede_stumble_visuals(self) -> None:
        resolver = re.search(
            r"func _resolve_visual_state.*?(?=\n\nfunc |\Z)",
            self.visual,
            re.DOTALL,
        )
        self.assertIsNotNone(resolver)
        source = resolver.group(0)
        airborne = source.index("if not grounded:")
        landing = source.index("if _landing_time > 0.0:")
        stumble = source.index("if locomotion == STATE_STUMBLE:")
        self.assertLess(airborne, stumble)
        self.assertLess(landing, stumble)

    def test_jump_and_fall_add_only_low_strength_ballet_line_over_native_clips(self) -> None:
        self.assertIn("func _apply_air_motion_overlay", self.retarget)
        self.assertIn("func _apply_air_port_de_bras", self.retarget)
        self.assertIn("func _apply_air_toe_line", self.retarget)
        self.assertIn('if state == &"JUMP":', self.retarget)
        self.assertIn('if state == &"AIRBORNE":', self.retarget)
        self.assertIn('if state != &"LANDING":', self.retarget)
        self.assertIn("var strength := 0.30", self.retarget)
        self.assertIn("var contact_strength := 0.28", self.retarget)

    def test_stumble_speed_changes_are_continuous_not_state_snaps(self) -> None:
        self.assertIn("STUMBLE_SPEED_MULTIPLIER := 0.68", self.dancer)
        self.assertIn("RECOVERY_SPEED_MULTIPLIER := 1.05", self.dancer)
        self.assertIn(
            "_locomotion_timer / STUMBLE_DURATION",
            self.dancer,
        )
        self.assertIn(
            "_locomotion_timer / RECOVERY_DURATION",
            self.dancer,
        )
        self.assertIn(
            "smoothstep(0.0, 0.72, progress)",
            self.dancer,
        )

    def test_opening_is_walk_then_turn_reverence_then_ready(self) -> None:
        self.assertIn("@export var entrance_walk_distance := 3.0", self.start_gate)
        self.assertIn(
            "entrance_start.x = entrance_target_x - maxf(entrance_walk_distance, 0.0)",
            self.start_gate,
        )
        walk = self.start_gate.index('_set_stage_visual(&"WALK")')
        bow = self.start_gate.index('_set_stage_visual(&"BOW")')
        ready = self.start_gate.index('_set_stage_visual(&"READY")')
        self.assertLess(walk, bow)
        self.assertLess(bow, ready)
        self.assertIn('next_state = STATE_STAGE_WALK', self.visual)
        self.assertIn('next_state = STATE_STAGE_BOW', self.visual)

    def test_running_stumble_is_forward_catch_step_not_a_stop(self) -> None:
        self.assertIn("STUMBLE_SPEED_MULTIPLIER := 0.68", self.dancer)
        self.assertIn("RECOVERY_SPEED_MULTIPLIER := 1.05", self.dancer)
        self.assertIn('&"STUMBLE": true', self.retarget)
        self.assertIn('&"RECOVERY": true', self.retarget)
        for token in (
            "_stumble_catch_pose",
            "_recovery_catch_pose",
            "_recovery_compress_pose",
            "_recovery_hop_pose",
            "_back_contact_pose()",
            "_front_brush_pose()",
        ):
            self.assertIn(token, self.source_v4)
        # The catch pitches the torso forward along +X while locomotion retains
        # a non-zero fraction of run speed.
        self.assertIn('"Rig/Pelvis/Torso:rotation": _rz(torso_angle)', self.source_v4)
        self.assertIn("_stumble_catch_pose(-0.075, -0.38)", self.source_v4)

    def test_finale_is_walk_bow_turn_walk_exit_in_that_order(self) -> None:
        for phase in ("WALK_TO_MARK", "FINAL_BOW", "EXIT_TURN", "EXIT_WALK"):
            self.assertIn(phase, self.recovery_manager)

        walk_1 = self.recovery_manager.index('_set_completion_stage_visual(&"WALK")')
        bow = self.recovery_manager.index('_set_completion_stage_visual(&"FINAL_BOW")')
        exit_turn = self.recovery_manager.index('_set_completion_stage_visual(&"EXIT_TURN")')
        walk_2 = self.recovery_manager.index(
            '_set_completion_stage_visual(&"WALK")',
            walk_1 + 1,
        )
        self.assertLess(walk_1, bow)
        self.assertLess(bow, exit_turn)
        self.assertLess(exit_turn, walk_2)
        self.assertIn("COMPLETION_APPROACH_DISTANCE := 1.60", self.recovery_manager)
        self.assertIn("COMPLETION_FINAL_BOW_DURATION := 2.60", self.recovery_manager)
        self.assertIn("COMPLETION_EXIT_TURN_DURATION := 0.38", self.recovery_manager)
        self.assertIn("COMPLETION_EXIT_WALK_DISTANCE := 7.00", self.recovery_manager)

    def test_finale_exit_turn_returns_audience_facing_to_positive_x(self) -> None:
        self.assertIn('STATE_STAGE_EXIT_TURN := &"STAGE_EXIT_TURN"', self.visual)
        self.assertIn("func _stage_exit_turn_animation() -> Animation:", self.visual)
        self.assertIn("_stage_ready_pose()", self.visual)
        self.assertIn("_stage_side_ready_pose()", self.visual)

        base = self._ry(math.pi * 0.5)
        audience_turn = self._ry(-math.pi * 0.5)
        visual_front = [0.0, 0.0, 1.0]
        audience_front = self._matmul(
            self._matmul(base, audience_turn),
            visual_front,
        )
        exit_front = self._matmul(base, visual_front)
        self.assertAlmostEqual(audience_front[2], 1.0, places=6)
        self.assertAlmostEqual(exit_front[0], 1.0, places=6)

    def test_closing_runway_has_room_for_bow_and_wing_exit(self) -> None:
        self.assertIn('size = Vector3(26, 0.5, 4)', self.course)
        self.assertIn(
            '[node name="NeutralClosingRunway" type="StaticBody3D" parent="Level"]\n'
            'position = Vector3(558, -3.05, 0)',
            self.course,
        )
        self.assertIn(
            '[node name="BackstageWingCurtain" type="MeshInstance3D" parent="Level"]\n'
            'position = Vector3(568, 0.45, 0)',
            self.course,
        )
        self.assertIn(
            '[node name="LevelCompleteTrigger" type="Marker3D" parent="Level"]\n'
            'position = Vector3(560, -2.8, 0)',
            self.course,
        )
        runway_end_x = 558.0 + 26.0 * 0.5
        exit_x = 560.0 + 1.60 + 7.00
        self.assertGreater(runway_end_x, exit_x)
        self.assertGreater(exit_x, 568.0)

    def test_stage_ending_controller_keeps_physics_and_walk_speed_owned_by_dancer(self) -> None:
        self.assertIn("func begin_stage_ending(speed: float = 0.0) -> void:", self.dancer)
        self.assertIn("func set_stage_ending_speed(speed: float) -> void:", self.dancer)
        self.assertIn("velocity.x = stage_entrance_speed", self.dancer)
        self.assertIn('dancer.call("begin_stage_ending", COMPLETION_WALK_SPEED)', self.recovery_manager)
        self.assertIn('dancer.call("set_stage_ending_speed", COMPLETION_WALK_SPEED)', self.recovery_manager)

    def test_humanoid_trip_uses_target_axis_independent_chain_directions(self) -> None:
        self.assertIn('_play_run_from_pending_contact(player, 0.94)', self.bootstrap)
        self.assertIn('_play_run_from_pending_contact(player, 1.03)', self.bootstrap)
        self.assertIn('current_world_basis', self.retarget)
        self.assertIn('parent_current.basis.get_rotation_quaternion().slerp', self.retarget)
        for token in (
            "func _apply_running_trip_overlay",
            "func _steer_current_chain_world_direction",
            "func _steer_current_segment_world_direction",
            "Quaternion(current_direction_world, desired)",
            'state == &"STUMBLE"',
            'state != &"RECOVERY"',
            "STUMBLE_DURATION := 0.24",
            "RECOVERY_DURATION := 0.62",
            "Vector3(0.48, 0.87, -0.05)",
            "Vector3(0.78, -0.42, -0.18)",
            "var catch_step_strength := 0.44 * sin(",
            "_trip_uses_left_foot",
        ):
            self.assertIn(token, self.retarget)
        self.assertIn("-0.050 * impact", self.retarget)


    def test_large_final_reverence_is_not_flattened_by_opening_curtsey_override(self) -> None:
        stage_calibration = re.search(
            r"func _apply_stage_presentation_calibration.*?(?=\n\nfunc |\Z)",
            self.retarget,
            re.DOTALL,
        )
        self.assertIsNotNone(stage_calibration)
        final_branch = re.search(
            r'\t\t&"STAGE_FINAL_BOW":(.*?)(?=\n\t\t&"|\Z)',
            stage_calibration.group(0),
            re.DOTALL,
        )
        self.assertIsNotNone(final_branch)
        self.assertIn("Final bow remains a separate next-stage quality pass.", final_branch.group(1))
        self.assertNotIn("_apply_classical_reverence_upper_body", final_branch.group(1))
        self.assertIn("func _stage_final_bow_animation() -> Animation:", self.visual)
        self.assertIn("_final_kneel_pose(-0.34, -0.58, 1.08)", self.visual)

    def test_ballerina_test_scene_has_live_completion_manager_contract(self) -> None:
        self.assertIn(
            'checkpoint_status_label = NodePath("../GameOverOverlay/Center/Panel/Actions/CheckpointStatus")',
            self.ballerina_test_scene,
        )
        self.assertIn(
            '[node name="CheckpointStatus" type="Label" parent="GameOverOverlay/Center/Panel/Actions"]',
            self.ballerina_test_scene,
        )

    def test_full_runtime_now_uses_ballerina_and_has_real_wing_exit(self) -> None:
        self.assertIn(
            'path="res://scenes/characters/ballerina_visual_v_1.tscn"',
            self.full_runtime,
        )
        self.assertIn(
            '[node name="BallerinaVisualV1" parent="Dancer" instance=ExtResource("35_ballerina")]',
            self.full_runtime,
        )
        self.assertIn(
            '[node name="BackstageWingCurtain" type="MeshInstance3D" parent="."]\n'
            'position = Vector3(568, 0.45, 0)',
            self.full_runtime,
        )
        self.assertIn(
            '[sub_resource type="BoxMesh" id="BoxMesh_202"]\n'
            'material = ExtResource("2_palace")\n'
            'size = Vector3(12.0000, 0.5000, 4.0000)',
            self.full_bridge,
        )
        full_runway_right = 564.064 + 12.0 * 0.5
        exit_x = 560.064 + 1.60 + 7.00
        self.assertGreater(full_runway_right, exit_x)
        self.assertGreater(exit_x, 568.0)

    def test_bootstrap_yields_choreography_states_to_retarget_layer(self) -> None:
        self.assertIn("handles_visual_state", self.bootstrap)
        self.assertIn("player.stop()", self.bootstrap)
        self.assertIn(
            'Callable(self, "_on_ballerina_visual_state_changed").bind(external_visual, player)',
            self.bootstrap,
        )


if __name__ == "__main__":
    unittest.main()
