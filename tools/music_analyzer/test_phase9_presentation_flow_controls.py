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

    def test_pause_stops_tree_and_audio_without_restarting_music(self) -> None:
        self.assertIn("get_tree().paused = paused", PAUSE)
        self.assertIn("audio_player.stream_paused = paused", PAUSE)
        self.assertNotIn("audio_player.stop()", PAUSE)
        self.assertIn("KEY_P", PAUSE)
        self.assertIn("KEY_ESCAPE", PAUSE)
        self.assertIn('name="PauseButton"', RUNTIME)
        self.assertIn('name="PauseOverlay"', RUNTIME)

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
