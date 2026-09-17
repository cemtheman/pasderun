from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MUSICALITY = ROOT / "scenes/gameplay/musicality.gd"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
TAP_FEEDBACK = ROOT / "scenes/gameplay/dancer_tap_feedback.gd"


class Phase8AudioTimingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.musicality = MUSICALITY.read_text(encoding="utf-8")
        cls.dancer = DANCER.read_text(encoding="utf-8")
        cls.feedback = TAP_FEEDBACK.read_text(encoding="utf-8")

    def test_existing_parameterless_tap_contract_is_preserved(self) -> None:
        self.assertIn("signal tap_detected", self.dancer)
        self.assertIn("tap_detected.emit()", self.dancer)
        self.assertIn("func _on_tap_detected() -> void:", self.feedback)

    def test_scoring_uses_touch_down_time(self) -> None:
        self.assertIn(
            "var playback_time := _tap_scoring_time()",
            self.musicality,
        )
        self.assertIn(
            'dancer.get("press_started_ms")',
            self.musicality,
        )
        self.assertIn(
            "Time.get_ticks_msec() - int(press_started_value)",
            self.musicality,
        )
        self.assertIn(
            "heard_time - press_duration",
            self.musicality,
        )

    def test_audio_clock_uses_mix_time_and_output_latency(self) -> None:
        self.assertIn(
            "AudioServer.get_time_since_last_mix()",
            self.musicality,
        )
        self.assertIn(
            "mixed_time - _output_latency",
            self.musicality,
        )

    def test_output_latency_is_cached_not_queried_per_frame(self) -> None:
        self.assertIn(
            "_output_latency = AudioServer.get_output_latency()",
            self.musicality,
        )
        self.assertEqual(
            self.musicality.count("AudioServer.get_output_latency()"),
            1,
        )

    def test_existing_timing_windows_are_unchanged(self) -> None:
        self.assertIn("const PERFECT_WINDOW := 0.12", self.musicality)
        self.assertIn("const GOOD_WINDOW := 0.28", self.musicality)
        self.assertIn("const EARLY_LATE_WINDOW := 0.50", self.musicality)


if __name__ == "__main__":
    unittest.main()
