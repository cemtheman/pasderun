from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ASSIST = ROOT / "scenes/gameplay/tap_timing_debug.gd"
MUSICALITY = ROOT / "scenes/gameplay/musicality.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
FLOW = ROOT / "scenes/gameplay/flow_tracker.gd"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
TIMELINE = ROOT / "scenes/gameplay/music_timeline.gd"
PLAN = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
COMPILER = ROOT / "tools/music_analyzer/compile_geometry.py"

TRUSTED = {
    FLOW: "55f7fc3df51fb387eeac6b57d66073adad23b34df668e30ab083a2a356853cbe",
    DANCER: "6068ec94ba4d99fa75180226f2d8cdf0a8172c868b9a4851c7214e1ce0b62748",
    TIMELINE: "605e9605c5a53ec84b862d4ce0b3893802fdfeb36f20dc09b3c67e3a5a183f68",
    PLAN: "6cc084749cc558659016cb5834da0fab8447c155918c16565a35666439ee1fd4",
    GENERATED: "2483eb3de87da79b2ad2ae3ccb734ca868898b3009e5861787be1853162ec7d4",
    COMPILER: "8dbd7e00769a83841b859813ba243169c941579a6c6f74dc1fa6b56dfefb0bae",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class TapTimingDebugTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.assist = ASSIST.read_text(encoding="utf-8")
        cls.musicality = MUSICALITY.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_runtime_wires_debug_only_timing_assist(self) -> None:
        self.assertIn('path="res://scenes/gameplay/tap_timing_debug.gd"', self.runtime)
        self.assertIn('name="TapTimingDebug" type="Node" parent="."', self.runtime)
        self.assertIn('name="TapTimingDebug" type="Label"', self.runtime)

    def test_accent_opportunity_source_is_musicality_only(self) -> None:
        self.assertIn('musicality.call("get_next_accent_opportunity", playback_time)', self.assist)
        self.assertIn("for index in ACCENT_MARKERS.size()", self.musicality)
        self.assertNotRegex(self.assist, r"\b(18|22|26)(\.0)?\b")

    def test_clock_is_music_timeline_playback(self) -> None:
        self.assertIn('music_timeline.call("get_playback_time")', self.assist)
        self.assertNotIn("Time.get_ticks", self.assist)
        self.assertNotIn("Timer", self.assist)

    def test_visual_windows_come_from_musicality_constants(self) -> None:
        self.assertIn('musicality.call("get_timing_windows")', self.assist)
        for key, constant in (
            ("perfect", "PERFECT_WINDOW"),
            ("good", "GOOD_WINDOW"),
            ("early_late", "EARLY_LATE_WINDOW"),
        ):
            self.assertIn(f'"{key}": {constant}', self.musicality)
            self.assertIn(f'windows["{key}"]', self.assist)

    def test_seek_restart_resets_feedback_and_musicality_consumption(self) -> None:
        rewind_guard = "playback_time + 0.05 < _last_playback_time"
        self.assertIn(rewind_guard, self.assist)
        self.assertIn('_last_classification = "—"', self.assist)
        self.assertIn(rewind_guard, self.musicality)
        self.assertIn("_consumed_accents.clear()", self.musicality)

    def test_cue_advances_and_finishes_without_duplicate_marker_state(self) -> None:
        self.assertIn("_consumed_accents.has(index)", self.musicality)
        self.assertIn("time <= marker_time + EARLY_LATE_WINDOW", self.musicality)
        self.assertIn("NO UPCOMING TAP OPPORTUNITY", self.assist)

    def test_assist_is_observational_and_never_generates_input(self) -> None:
        for forbidden in ("Input.", "tap_detected.emit", "accent_evaluated.emit", "_on_tap_detected"):
            self.assertNotIn(forbidden, self.assist)
        self.assertNotIn("flow_value", self.assist)

    def test_classification_logic_and_tuning_are_unchanged(self) -> None:
        self.assertIn("const ACCENT_MARKERS: Array[float] = [18.0, 22.0, 26.0]", self.musicality)
        self.assertIn("const PERFECT_WINDOW := 0.12", self.musicality)
        self.assertIn("const GOOD_WINDOW := 0.28", self.musicality)
        self.assertIn("const EARLY_LATE_WINDOW := 0.50", self.musicality)
        classification = re.search(
            r"func _classify_delta\(delta: float\).*?(?=\n\nfunc )",
            self.musicality,
            re.DOTALL,
        )
        self.assertIsNotNone(classification)
        self.assertIn("absolute_delta <= PERFECT_WINDOW", classification.group(0))
        self.assertIn("absolute_delta <= GOOD_WINDOW", classification.group(0))

    def test_trusted_flow_movement_music_geometry_and_compiler_are_unchanged(self) -> None:
        for path, expected in TRUSTED.items():
            self.assertEqual(digest(path), expected, path)


if __name__ == "__main__":
    unittest.main()
