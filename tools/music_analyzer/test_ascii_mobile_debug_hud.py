from __future__ import annotations

import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TIMING = ROOT / "scenes/gameplay/tap_timing_debug.gd"
TRACE = ROOT / "scenes/gameplay/accent_runtime_trace.gd"
SANITIZER = ROOT / "scenes/gameplay/ascii_debug_hud.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
FLOW = ROOT / "scenes/gameplay/flow_tracker.gd"
MUSICALITY = ROOT / "scenes/gameplay/musicality.gd"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
CAMERA = ROOT / "scenes/gameplay/generated/fork_camera_framing.gd"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"

TRUSTED = {
    FLOW: "90e1ff56977a8c93198d3d9b1fc932f3edef945b38ad1eb902555f0deb20fb3a",
    MUSICALITY: "d08a1db94883f79aabb48640f0d194fbf70f99c30a8459d504621243d06bff81",
    DANCER: "6068ec94ba4d99fa75180226f2d8cdf0a8172c868b9a4851c7214e1ce0b62748",
    CAMERA: "8b14a565bd8d1f45189a4b7801855c8159847545a43f1cba276f19a5da2022e1",
    GENERATED: "2ede8fcbd2a7158332c1656459a0e41e12886a8af4c3101576131713ef6ca4e6",
}

FORBIDDEN = ("●", "━", "─", "═", "│", "→", "←", "↑", "↓", "—")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AsciiMobileDebugHudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.timing = TIMING.read_text(encoding="utf-8")
        cls.trace = TRACE.read_text(encoding="utf-8")
        cls.sanitizer = SANITIZER.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_timing_trace_and_scene_defaults_are_ascii_safe(self) -> None:
        for source in (self.timing, self.trace, self.runtime):
            for character in FORBIDDEN:
                self.assertNotIn(character, source)

    def test_timing_indicator_remains_readable_and_moving(self) -> None:
        for character in ('"-"', '"="', '"#"', '"|"', '"o"'):
            self.assertIn(character, self.timing)
        self.assertIn("marker_position", self.timing)
        self.assertIn("EARLY      PERFECT      LATE", self.timing)
        self.assertIn(">>> TAP NOW - %s <<<", self.timing)

    def test_runtime_hud_filters_debug_text_without_touching_gameplay_sources(self) -> None:
        self.assertIn('path="res://scenes/gameplay/ascii_debug_hud.gd"', self.runtime)
        self.assertIn('script = ExtResource("12_ascii_hud")', self.runtime)
        self.assertIn("ASCII_REPLACEMENTS", self.sanitizer)
        self.assertIn("String.chr(codepoint)", self.sanitizer)
        self.assertNotIn("Input.", self.sanitizer)
        self.assertNotIn("flow_value", self.sanitizer)

    def test_gameplay_music_geometry_and_camera_sources_are_unchanged(self) -> None:
        for path, expected in TRUSTED.items():
            self.assertEqual(digest(path), expected, path)


if __name__ == "__main__":
    unittest.main()
