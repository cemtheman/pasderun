from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RECOVERY = (ROOT / "scenes/gameplay/run_recovery_manager.gd").read_text(encoding="utf-8")
DANCER = (ROOT / "scenes/gameplay/dancer.gd").read_text(encoding="utf-8")
RUNTIME = (
    ROOT / "scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"
).read_text(encoding="utf-8")


class Phase112EndOfPieceTransitionTests(unittest.TestCase):
    def test_run_to_walk_handoff_begins_before_stream_end(self) -> None:
        self.assertIn("func _should_begin_completion_lead() -> bool:", RECOVERY)
        self.assertIn("audio_player.stream.get_length()", RECOVERY)
        self.assertIn("audio_player.get_playback_position()", RECOVERY)
        self.assertIn(
            "return remaining <= COMPLETION_DECEL_DURATION",
            RECOVERY,
        )

        process = RECOVERY.index("func _physics_process(delta: float) -> void:")
        lead = RECOVERY.index("_should_begin_completion_lead()", process)
        fallback = RECOVERY.index("and not audio_player.playing", process)
        self.assertLess(lead, fallback)

    def test_deceleration_resolves_to_walk_not_post_music_run(self) -> None:
        self.assertIn("COMPLETION_DECEL_DURATION := 1.20", RECOVERY)
        self.assertIn("COMPLETION_WALK_SPEED := 1.45", RECOVERY)
        self.assertIn("COMPLETION_WALK_VISUAL_SWITCH := 0.65", RECOVERY)
        self.assertIn(
            '_set_completion_stage_visual(&"RUN")',
            RECOVERY,
        )
        self.assertIn(
            '_set_completion_stage_visual(&"WALK")',
            RECOVERY,
        )

        decel = RECOVERY.index("CompletionPhase.DECELERATE_TO_WALK:")
        switch = RECOVERY.index(
            "if t >= COMPLETION_WALK_VISUAL_SWITCH:",
            decel,
        )
        walk = RECOVERY.index("CompletionPhase.WALK_TO_MARK:", decel)
        self.assertLess(decel, switch)
        self.assertLess(switch, walk)

    def test_post_music_walk_is_short_and_not_forced_to_old_music_end_x(self) -> None:
        match = re.search(
            r'\[node name="SliceCompletion".*?position = Vector3\(([^,]+),',
            RUNTIME,
            re.S,
        )
        self.assertIsNotNone(match)
        completion_x = float(match.group(1))
        self.assertAlmostEqual(completion_x / 4.0, 140.016, places=4)

        self.assertIn("COMPLETION_APPROACH_DISTANCE := 0.55", RECOVERY)
        begin = RECOVERY.index("func _begin_completion_ceremony() -> void:")
        update = RECOVERY.index("func _update_completion_ceremony", begin)
        begin_block = RECOVERY[begin:update]
        self.assertNotIn("completion_trigger.global_position.x", begin_block)
        self.assertIn(
            '_set_completion_stage_visual(&"FINAL_BOW")',
            RECOVERY,
        )

    def test_final_reverence_is_terminal_stage_image(self) -> None:
        self.assertNotIn("EXIT_TURN,", RECOVERY)
        self.assertNotIn("EXIT_WALK,", RECOVERY)
        self.assertNotIn("COMPLETION_EXIT_WALK_DISTANCE", RECOVERY)
        self.assertNotIn("COMPLETION_EXIT_TURN_DURATION", RECOVERY)

        final = RECOVERY.index("CompletionPhase.FINAL_BOW:")
        finish = RECOVERY.index("_finish_level_complete_state()", final)
        next_function = RECOVERY.index(
            "func _set_completion_stage_visual",
            final,
        )
        final_block = RECOVERY[final:next_function]
        self.assertLess(finish, next_function)
        self.assertNotIn('_set_completion_stage_visual(&"EXIT_TURN")', final_block)
        self.assertNotIn('_set_completion_stage_visual(&"WALK")', final_block)

    def test_music_finished_remains_safe_fallback(self) -> None:
        callback = RECOVERY.index("func _on_music_finished() -> void:")
        helper = RECOVERY.index("func _should_begin_completion_lead() -> bool:")
        block = RECOVERY[callback:helper]
        self.assertIn("_state != RunState.PLAYING", block)
        self.assertIn("_begin_completion_ceremony()", block)

    def test_stage_ending_keeps_real_grounding_and_blocks_gameplay(self) -> None:
        self.assertIn("var stage_ending_mode := false", DANCER)
        self.assertIn("func begin_stage_ending(speed: float = 0.0) -> void:", DANCER)
        self.assertIn("stage_entrance_mode or stage_ending_mode", DANCER)
        self.assertIn("_physics_process_stage_entrance(delta)", DANCER)


if __name__ == "__main__":
    unittest.main()
