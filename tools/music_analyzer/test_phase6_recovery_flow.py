from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DANCER = ROOT / "scenes/gameplay/dancer.gd"
FLOW = ROOT / "scenes/gameplay/flow_tracker.gd"
MUSICALITY = ROOT / "scenes/gameplay/musicality.gd"
RECOVERY = ROOT / "scenes/gameplay/run_recovery_manager.gd"
CAMERA = ROOT / "scenes/gameplay/fork_camera_controller.gd"
PROBE = ROOT / "scenes/gameplay/spatial_stall_probe.gd"
HUD = ROOT / "scenes/gameplay/ascii_debug_hud.gd"
FORK_DEBUG = ROOT / "scenes/gameplay/generated/fork_debug_visualization.gd"
DEMANDS = ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json"
RUNTIME_SCENE = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"


def function(source: str, name: str) -> str:
    match = re.search(rf"func {name}\(.*?(?=\n\nfunc |\Z)", source, re.DOTALL)
    if match is None:
        raise AssertionError(f"missing function {name}")
    return match.group(0)


class Phase6RecoveryFlowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dancer = DANCER.read_text(encoding="utf-8")
        cls.flow = FLOW.read_text(encoding="utf-8")
        cls.musicality = MUSICALITY.read_text(encoding="utf-8")
        cls.recovery = RECOVERY.read_text(encoding="utf-8")

    def test_locomotion_state_contract_is_deterministic(self) -> None:
        for state in ("NORMAL", "STUMBLE", "RECOVERY"):
            self.assertIn(state, self.dancer)
        update = function(self.dancer, "_update_locomotion_state")
        self.assertIn("STUMBLE_DURATION", self.dancer)
        self.assertIn("RECOVERY_DURATION", self.dancer)
        self.assertIn("LocomotionState.RECOVERY", update)
        self.assertIn("LocomotionState.NORMAL", update)
        self.assertNotIn("rand", update.lower())

    def test_successful_gap_jump_is_exempt_from_drop_stumble(self) -> None:
        jump = function(self.dancer, "_jump")
        outcome = function(self.dancer, "_handle_motion_outcome")
        self.assertIn("_jump_in_progress = true", jump)
        self.assertIn("if not _jump_in_progress and drop_distance >= VALID_DROP_MINIMUM", outcome)
        self.assertIn("_jump_in_progress = false", outcome)

    def test_valid_lower_drop_triggers_one_stumble(self) -> None:
        outcome = function(self.dancer, "_handle_motion_outcome")
        trigger = function(self.dancer, "_trigger_stumble")
        self.assertIn('_trigger_stumble(&"LOWER_ROUTE_DROP")', outcome)
        self.assertIn("locomotion_state != LocomotionState.NORMAL", trigger)
        self.assertEqual(trigger.count("stumble_started.emit(reason)"), 1)

    def test_platform_edge_impact_triggers_recoverable_stumble(self) -> None:
        outcome = function(self.dancer, "_handle_motion_outcome")
        self.assertIn("normal.x < -0.55", outcome)
        self.assertIn('_trigger_stumble(&"PLATFORM_EDGE")', outcome)

    def test_small_step_uses_wall_safe_clearance_probe_and_forward_traversal(self) -> None:
        step = function(self.dancer, "_attempt_small_step")
        outcome = function(self.dancer, "_handle_motion_outcome")
        self.assertIn("MAX_TRAVERSABLE_STEP_HEIGHT", step)
        self.assertIn("STEP_PROBE_BACKOFF", step)
        self.assertIn("probe_transform.origin.x -= STEP_PROBE_BACKOFF", step)
        self.assertIn("raised_transform := probe_transform", step)
        self.assertGreaterEqual(step.count("test_move("), 2)
        self.assertIn("move_and_collide(forward_motion)", step)
        self.assertIn("move_and_collide(Vector3.DOWN * MAX_TRAVERSABLE_STEP_HEIGHT)", step)
        self.assertIn("STEP_FORWARD_CLEARANCE", step)
        self.assertIn("actual_forward", outcome)
        self.assertIn("stalled_forward", outcome)
        self.assertIn("hit_forward_edge or stalled_forward", outcome)

    def test_recovery_is_observable_and_catches_up_without_course_music_drift(self) -> None:
        stumble_duration = float(re.search(r"const STUMBLE_DURATION := ([0-9.]+)", self.dancer).group(1))
        recovery_duration = float(re.search(r"const RECOVERY_DURATION := ([0-9.]+)", self.dancer).group(1))
        stumble_multiplier = float(re.search(r"const STUMBLE_SPEED_MULTIPLIER := ([0-9.]+)", self.dancer).group(1))
        recovery_multiplier = float(re.search(r"const RECOVERY_SPEED_MULTIPLIER := ([0-9.]+)", self.dancer).group(1))
        weighted_multiplier = (
            stumble_duration * stumble_multiplier + recovery_duration * recovery_multiplier
        ) / (stumble_duration + recovery_duration)
        self.assertGreater(stumble_multiplier, 0.0)
        self.assertLess(stumble_multiplier, 1.0)
        self.assertGreater(recovery_multiplier, 1.0)
        self.assertAlmostEqual(weighted_multiplier, 1.0, delta=0.01)
        physics = function(self.dancer, "_physics_process")
        visual = function(self.dancer, "_update_locomotion_visual")
        self.assertIn("run_speed * _locomotion_speed_multiplier()", physics)
        self.assertIn("_update_locomotion_visual(delta)", physics)
        self.assertIn("STUMBLE_VISUAL_TILT_RADIANS", visual)
        self.assertIn("body_mesh.rotation.z", visual)

    def test_one_stumble_has_one_existing_phrase_break_consequence(self) -> None:
        callback = function(self.flow, "_on_stumble_started")
        self.assertEqual(callback.count("_apply_reduction("), 1)
        self.assertIn('REDUCTIONS[&"PHRASE_BREAK"]', callback)
        self.assertIn('dancer.connect(&"stumble_started"', self.flow)

    def test_edge_stumble_does_not_double_charge_poor_landing(self) -> None:
        callback = function(self.flow, "_on_stumble_started")
        jumps = function(self.flow, "_track_jump_events")
        self.assertIn('reason == &"PLATFORM_EDGE"', callback)
        self.assertIn("if _suppress_next_poor_landing:", jumps)
        self.assertIn('REDUCTIONS[&"POOR_LANDING"]', jumps)

    def test_checkpoint_records_actual_safe_grounded_position(self) -> None:
        update = function(self.recovery, "_update_checkpoint")
        self.assertIn('fork_camera_controller.call("is_outside_fork")', update)
        self.assertIn("_checkpoint_position = dancer.global_position", update)
        self.assertIn(
            "_checkpoint_music_time = dancer.global_position.x / RUN_SPEED",
            update,
        )
        self.assertNotIn("CHECKPOINT_SURFACE_Y + DANCER_STANDING_OFFSET", update)
        self.assertNotIn('float(candidate["x"]) / RUN_SPEED', update)

    def test_existing_death_continue_restart_and_completion_remain_authoritative(self) -> None:
        self.assertIn("const DEATH_Y := -6.0", self.recovery)
        physics = function(self.recovery, "_physics_process")
        self.assertLess(physics.index("completion_trigger.global_position.x"), physics.index("DEATH_Y"))
        self.assertIn("_enter_dead_state()", physics)
        self.assertIn("_continue_from_checkpoint", self.recovery)
        self.assertIn("_restart_run", self.recovery)
        self.assertIn("RunState.LEVEL_COMPLETE", self.recovery)
        restore = function(self.recovery, "_restore_dancer")
        self.assertIn('dancer.call("reset_locomotion_state")', restore)

    def test_full_course_markers_come_from_existing_musical_demands(self) -> None:
        self.assertIn("movement_demands_path", self.musicality)
        loader = function(self.musicality, "_load_accent_markers")
        for field in ("accent_strength", "boundary_strength", "climax_strength"):
            self.assertIn(field, loader)
        self.assertNotIn("Timer", loader)

    def test_remaining_course_coverage_has_no_ten_second_hole(self) -> None:
        demands = json.loads(DEMANDS.read_text(encoding="utf-8"))
        times = [18.0, 22.0, 26.0]
        for event in demands["events"]:
            context = event["musical_context"]
            if event["time"] > 30.0 and (
                context["accent_strength"] >= 0.72
                or context["boundary_strength"] >= 0.85
                or context["climax_strength"] >= 0.88
            ):
                times.append(float(event["time"]))
        gaps = [later - earlier for earlier, later in zip(times, times[1:])]
        self.assertGreaterEqual(times[-1], 135.0)
        self.assertLess(max(gaps), 10.0)


    def test_full_course_tap_markers_are_wired_into_live_runtime_scene(self) -> None:
        runtime = RUNTIME_SCENE.read_text(encoding="utf-8")
        self.assertIn('path="res://scenes/gameplay/musicality.gd"', runtime)
        self.assertIn('[node name="Musicality" type="Node" parent="Music"', runtime)
        self.assertIn('music_timeline = NodePath("../MusicTimeline")', runtime)
        self.assertIn('dancer = NodePath("../../Dancer")', runtime)
        tap_debug = (ROOT / "scenes/gameplay/tap_timing_debug.gd").read_text(encoding="utf-8")
        self.assertIn('musicality.call("get_next_accent_opportunity", playback_time)', tap_debug)

    def test_timing_windows_and_flow_tuning_are_unchanged(self) -> None:
        for line in (
            "const PERFECT_WINDOW := 0.12",
            "const GOOD_WINDOW := 0.28",
            "const EARLY_LATE_WINDOW := 0.50",
            "const MISS_RETAINED_FRACTION := 0.60",
            '&"PHRASE_BREAK": 0.06',
        ):
            self.assertIn(line, self.musicality + self.flow)

    def test_camera_and_course_geometry_are_not_touched_by_phase6_logic(self) -> None:
        for forbidden in ("Camera3D", "look_ahead", "SafeLowerRoute", "TechnicalRoute"):
            self.assertNotIn(forbidden, self.dancer + self.flow + self.musicality)
        self.assertIn("APPROACHING_FORK", CAMERA.read_text(encoding="utf-8"))

    def test_debug_controls_and_web_label_safety_remain_intact(self) -> None:
        probe = PROBE.read_text(encoding="utf-8")
        self.assertIn("KEY_F", probe)
        self.assertIn("KEY_V", probe)
        self.assertIn("KEY_B", probe)
        self.assertIn("KEY_H", HUD.read_text(encoding="utf-8"))
        self.assertIn("WEB LABELS OFF", FORK_DEBUG.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
