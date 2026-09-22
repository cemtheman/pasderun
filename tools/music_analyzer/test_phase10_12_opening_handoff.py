from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scenes" / "gameplay" / "runtime_start_gate.gd"
CONTROLLER = ROOT / "scenes" / "characters" / "humanoid_motion_controller.gd"
DANCER = ROOT / "scenes" / "gameplay" / "dancer.gd"


class Phase1012OpeningHandoffTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gate = GATE.read_text(encoding="utf-8")
        cls.controller = CONTROLLER.read_text(encoding="utf-8")
        cls.dancer = DANCER.read_text(encoding="utf-8")

    def test_prelude_has_explicit_exit_turn_between_ready_and_started(self) -> None:
        enum = re.search(
            r"enum PreludeState \{.*?\}",
            self.gate,
            re.DOTALL,
        )
        self.assertIsNotNone(enum)
        source = enum.group(0)
        self.assertLess(source.index("READY"), source.index("EXIT_TURN"))
        self.assertLess(source.index("EXIT_TURN"), source.index("STARTED"))

    def test_opening_bow_and_ready_remain_audience_facing(self) -> None:
        bow = re.search(
            r"func _apply_opening_reverence\(\).*?(?=\n\nfunc |\Z)",
            self.controller,
            re.DOTALL,
        )
        ready = re.search(
            r"func _apply_stage_ready\(\).*?(?=\n\nfunc |\Z)",
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(bow)
        self.assertIsNotNone(ready)
        self.assertIn("_set_stage_orientation(turn_in)", bow.group(0))
        self.assertNotIn("turn_out", bow.group(0))
        self.assertIn("_set_stage_orientation(1.0)", ready.group(0))

    def test_start_input_commits_exit_turn_without_releasing_gameplay(self) -> None:
        handler = re.search(
            r"func _input\(.*?(?=\n\nfunc |\Z)",
            self.gate,
            re.DOTALL,
        )
        self.assertIsNotNone(handler)
        source = handler.group(0)
        self.assertIn("_prelude_state = PreludeState.EXIT_TURN", source)
        self.assertIn('_set_stage_visual(&"EXIT_TURN")', source)
        self.assertIn("audio_player.play(0.0)", source)
        self.assertIn("audio_player.stream_paused = true", source)
        self.assertNotIn('dancer.call("end_stage_entrance")', source)
        self.assertNotIn("runtime_started.emit()", source)
        self.assertNotIn("audio_player.stream_paused = false", source)

    def test_exit_turn_duration_is_owned_by_visual_authority(self) -> None:
        self.assertIn(
            "func get_stage_exit_turn_duration() -> float:",
            self.controller,
        )
        self.assertIn(
            "return STAGE_EXIT_TURN_DURATION",
            self.controller,
        )
        self.assertIn(
            '_stage_visual.has_method("get_stage_exit_turn_duration")',
            self.gate,
        )
        self.assertIn(
            '_stage_visual.call("get_stage_exit_turn_duration")',
            self.gate,
        )

    def test_gameplay_and_music_release_only_after_exit_turn(self) -> None:
        process = re.search(
            r"func _process\(.*?(?=\n\nfunc |\Z)",
            self.gate,
            re.DOTALL,
        )
        release = re.search(
            r"func _enable_gameplay_after_exit_turn\(\).*?(?=\n\nfunc |\Z)",
            self.gate,
            re.DOTALL,
        )
        self.assertIsNotNone(process)
        self.assertIsNotNone(release)
        self.assertIn(
            "if _prelude_state == PreludeState.EXIT_TURN:",
            process.group(0),
        )
        self.assertIn(
            "if _exit_turn_elapsed >= _exit_turn_duration:",
            process.group(0),
        )
        self.assertIn(
            "_enable_gameplay_after_exit_turn()",
            process.group(0),
        )

        source = release.group(0)
        end_stage = source.index('dancer.call("end_stage_entrance")')
        clear_stage = source.index('clear_stage_presentation')
        seek_zero = source.index("audio_player.seek(0.0)")
        signal = source.index("runtime_started.emit()")
        unpause = source.index("audio_player.stream_paused = false")
        self.assertLess(end_stage, clear_stage)
        self.assertLess(clear_stage, seek_zero)
        self.assertLess(seek_zero, signal)
        self.assertLess(signal, unpause)

    def test_dancer_remains_stationary_stage_authority_during_turn(self) -> None:
        self.assertIn(
            "if stage_entrance_mode or stage_ending_mode:",
            self.dancer,
        )
        self.assertIn(
            "_physics_process_stage_entrance(delta)",
            self.dancer,
        )
        self.assertIn(
            "velocity.x = stage_entrance_speed",
            self.dancer,
        )
        self.assertIn(
            'dancer.call("set_stage_entrance_speed", 0.0)',
            self.gate,
        )


if __name__ == "__main__":
    unittest.main()
