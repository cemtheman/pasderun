from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
START = (ROOT / "scenes/gameplay/runtime_start_gate.gd").read_text(encoding="utf-8")
DANCER = (ROOT / "scenes/gameplay/dancer.gd").read_text(encoding="utf-8")
VISUAL = (ROOT / "scenes/gameplay/dancer_visual.gd").read_text(encoding="utf-8")
PAUSE = (ROOT / "scenes/gameplay/pause_controller.gd").read_text(encoding="utf-8")
RECOVERY = (ROOT / "scenes/gameplay/run_recovery_manager.gd").read_text(encoding="utf-8")
CHECKPOINT = (ROOT / "scenes/gameplay/checkpoint_visualization.gd").read_text(encoding="utf-8")
RUNTIME = (ROOT / "scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn").read_text(encoding="utf-8")


class Phase9PresentationFlowControlsTests(unittest.TestCase):
    def test_silent_stage_entrance_precedes_music_start(self) -> None:
        self.assertIn("PreludeState.WALK_IN", START)
        self.assertIn("PreludeState.BOW", START)
        self.assertIn("PreludeState.READY", START)
        self.assertIn('audio_player.play(0.0)', START)
        self.assertIn('audio_player.stream_paused = true', START)
        self.assertIn('audio_player.stream_paused = false', START)
        play_pos = START.index('audio_player.play(0.0)')
        hold_pos = START.index('audio_player.stream_paused = true', play_pos)
        release_pos = START.index('audio_player.stream_paused = false', hold_pos)
        deferred_pos = START.index('func _enable_gameplay_after_start_input() -> void:')
        rewind_pos = START.index('audio_player.seek(0.0)', deferred_pos)
        self.assertLess(play_pos, hold_pos)
        self.assertLess(deferred_pos, rewind_pos)
        self.assertLess(rewind_pos, release_pos)
        self.assertIn('overlay.visible = false', START)
        self.assertIn('dancer.call("begin_stage_entrance", entrance_speed)', START)
        self.assertIn('transform = Transform3D(1, 0, 0, 0, 1, 0, 0, 0, 1, -3.2, 1.5, 0)', RUNTIME)

    def test_stage_entrance_uses_real_grounding_and_dedicated_visual_states(self) -> None:
        self.assertIn("stage_entrance_mode", DANCER)
        self.assertIn("_physics_process_stage_entrance", DANCER)
        self.assertIn("move_and_slide()", DANCER)
        for token in ("STATE_STAGE_WALK", "STATE_STAGE_BOW", "STATE_STAGE_READY"):
            self.assertIn(token, VISUAL)
        self.assertIn("_stage_bow_animation", VISUAL)
        self.assertIn("_stage_walk_animation", VISUAL)
        self.assertIn('"Rig:rotation"', VISUAL)
        self.assertIn("const FOURTH_WALL_YAW := -PI * 0.5", VISUAL)
        self.assertIn("_stage_fourth_wall_turn_pose()", VISUAL)
        self.assertIn('"Rig:rotation": _ry(FOURTH_WALL_YAW)', VISUAL)

    def test_fourth_wall_presentation_morph_preserves_humanoid_proportions(self) -> None:
        self.assertIn("_set_front_presentation_geometry(front_facing)", VISUAL)
        self.assertIn("arm_back.position = Vector3(0.0, 0.52, 0.20)", VISUAL)
        self.assertIn("arm_front.position = Vector3(0.0, 0.52, -0.20)", VISUAL)
        self.assertIn("leg_back.position = Vector3(0.0, -0.08, 0.075)", VISUAL)
        self.assertIn("torso_shape.scale = Vector3(1.0, 1.0, 1.80)", VISUAL)
        self.assertIn("pelvis_shape.scale = Vector3(1.0, 1.0, 1.40)", VISUAL)
        self.assertIn("func _rx(angle: float)", VISUAL)
        self.assertIn('"Rig/Pelvis/Torso/ArmBackShoulder:rotation": _rx(-0.24)', VISUAL)
        self.assertIn("_set_front_presentation_geometry(false)", VISUAL)

    def test_final_completion_waits_for_large_kneeling_reverence(self) -> None:
        self.assertIn("COMPLETION_CEREMONY", RECOVERY)
        self.assertIn("COMPLETION_CEREMONY_DURATION := 2.60", RECOVERY)
        self.assertIn("_begin_completion_ceremony()", RECOVERY)
        self.assertIn("_finish_level_complete_state()", RECOVERY)
        self.assertIn('dancer.call("begin_stage_ending")', RECOVERY)
        self.assertIn(
            '_dancer_visual.call("set_stage_presentation_state", &"FINAL_BOW")',
            RECOVERY,
        )
        self.assertIn("STATE_STAGE_FINAL_BOW", VISUAL)
        self.assertIn("_stage_final_bow_animation", VISUAL)
        self.assertIn("_final_kneel_pose", VISUAL)
        self.assertIn('"Rig/Pelvis/LegBackHip/LegBackKnee:rotation": _rx(-1.30)', VISUAL)

    def test_final_reverence_does_not_cut_soundtrack_early(self) -> None:
        begin = RECOVERY.index("func _begin_completion_ceremony() -> void:")
        finish = RECOVERY.index("func _finish_level_complete_state() -> void:")
        begin_block = RECOVERY[begin:finish]
        finish_block = RECOVERY[finish:]
        self.assertNotIn("audio_player.stop()", begin_block)
        self.assertIn("audio_player.stop()", finish_block)

    def test_final_ceremony_blocks_gameplay_input_but_keeps_grounding(self) -> None:
        self.assertIn("var stage_ending_mode := false", DANCER)
        self.assertIn("func begin_stage_ending()", DANCER)
        self.assertIn("stage_entrance_mode or stage_ending_mode", DANCER)
        self.assertIn("_physics_process_stage_entrance(delta)", DANCER)

    def test_pause_stops_tree_and_audio_without_restarting_music(self) -> None:
        self.assertIn("get_tree().paused = true", PAUSE)
        self.assertIn("get_tree().paused = false", PAUSE)
        self.assertIn("audio_player.stream_paused = true", PAUSE)
        self.assertIn("audio_player.stream_paused = false", PAUSE)
        self.assertNotIn("audio_player.stop()", PAUSE)
        self.assertIn("KEY_P", PAUSE)
        self.assertIn("KEY_ESCAPE", PAUSE)
        self.assertIn('name="PauseButton"', RUNTIME)
        self.assertIn('name="PauseOverlay"', RUNTIME)

    def test_pause_resume_restores_captured_music_position(self) -> None:
        self.assertIn("var _paused_audio_position := 0.0", PAUSE)
        self.assertIn("_paused_audio_position = audio_player.get_playback_position()", PAUSE)
        self.assertIn("audio_player.seek(_paused_audio_position)", PAUSE)
        self.assertIn("audio_player.play(_paused_audio_position)", PAUSE)
        self.assertNotIn("audio_player.play(0.0)", PAUSE)

    def test_pause_buttons_never_capture_space_focus(self) -> None:
        self.assertIn("pause_button.focus_mode = Control.FOCUS_NONE", PAUSE)
        self.assertIn("resume_button.focus_mode = Control.FOCUS_NONE", PAUSE)
        self.assertIn("pause_button.release_focus()", PAUSE)
        self.assertIn("resume_button.release_focus()", PAUSE)
        self.assertIn('focus_mode = 0\ntext = "II"', RUNTIME)
        self.assertIn('focus_mode = 0\ntext = "RESUME"', RUNTIME)

    def test_checkpoint_3d_visuals_are_disabled_at_creation_boundary_on_web(self) -> None:
        self.assertIn('_web_visuals_disabled := OS.has_feature("web")', CHECKPOINT)
        self.assertIn("if _web_visuals_disabled:", CHECKPOINT)
        ready_start = CHECKPOINT.index("func _ready() -> void:")
        connect_start = CHECKPOINT.index("recovery_manager.connect(", ready_start)
        ready_prefix = CHECKPOINT[ready_start:connect_start]
        self.assertIn("return", ready_prefix)

    def test_checkpoint_marker_uses_exact_captured_respawn_position(self) -> None:
        self.assertIn("signal checkpoint_changed", RECOVERY)
        self.assertIn("_checkpoint_position = dancer.global_position", RECOVERY)
        self.assertIn("checkpoint_changed.emit(", RECOVERY)
        self.assertIn("checkpoint_position.x", CHECKPOINT)
        self.assertIn("checkpoint_position.y - 1.12", CHECKPOINT)
        self.assertIn("CheckpointMarker", CHECKPOINT)
        self.assertIn("CheckpointStatus", RUNTIME)

    def test_start_checkpoint_is_recaptured_after_stage_entrance(self) -> None:
        self.assertIn("func _on_runtime_started()", RECOVERY)
        self.assertIn("_checkpoint_index = 0", RECOVERY)
        self.assertIn("_checkpoint_music_time = 0.0", RECOVERY)
        self.assertIn("_checkpoint_position = dancer.global_position", RECOVERY)


if __name__ == "__main__":
    unittest.main()
