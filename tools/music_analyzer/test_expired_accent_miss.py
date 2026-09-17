from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MUSICALITY = ROOT / "scenes/gameplay/musicality.gd"
TRACE = ROOT / "scenes/gameplay/accent_runtime_trace.gd"
FLOW = ROOT / "scenes/gameplay/flow_tracker.gd"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
PLAN = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
CAMERA = ROOT / "scenes/gameplay/generated/fork_camera_framing.gd"

TRUSTED = {
    FLOW: "90e1ff56977a8c93198d3d9b1fc932f3edef945b38ad1eb902555f0deb20fb3a",
    DANCER: "6068ec94ba4d99fa75180226f2d8cdf0a8172c868b9a4851c7214e1ce0b62748",
    PLAN: "6cc084749cc558659016cb5834da0fab8447c155918c16565a35666439ee1fd4",
    GENERATED: "2ede8fcbd2a7158332c1656459a0e41e12886a8af4c3101576131713ef6ca4e6",
    CAMERA: "8b14a565bd8d1f45189a4b7801855c8159847545a43f1cba276f19a5da2022e1",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ExpiredAccentMissTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.source = MUSICALITY.read_text(encoding="utf-8")
        cls.trace = TRACE.read_text(encoding="utf-8")
        cls.expiry = re.search(
            r"func _expire_missed_accents\(.*?(?=\n\nfunc )",
            cls.source,
            re.DOTALL,
        ).group(0)
        cls.tap = re.search(
            r"func _on_tap_detected\(\).*?(?=\n\nfunc )",
            cls.source,
            re.DOTALL,
        ).group(0)

    def test_skipped_accent_emits_miss_only_after_full_window(self) -> None:
        self.assertIn("expiry_time := marker_time + EARLY_LATE_WINDOW", self.expiry)
        self.assertIn("playback_time > expiry_time", self.expiry)
        self.assertIn('accent_evaluated.emit(&"MISS", delta, marker_time)', self.expiry)
        self.assertIn('&"NONE"', self.expiry)

    def test_marker_is_consumed_before_expired_miss_emit(self) -> None:
        consume = self.expiry.index("_consumed_accents[index] = true")
        emit = self.expiry.index('accent_evaluated.emit(&"MISS"')
        self.assertLess(consume, emit)
        self.assertIn("if _consumed_accents.has(index):", self.expiry)

    def test_timely_tap_consumption_prevents_expired_miss(self) -> None:
        self.assertIn("_consumed_accents[accent_index] = true", self.tap)
        self.assertIn("if _consumed_accents.has(index):", self.expiry)

    def test_existing_classifications_and_tap_miss_are_unchanged(self) -> None:
        self.assertIn('accent_evaluated.emit(&"MISS", 0.0, -1.0)', self.tap)
        self.assertIn('accent_evaluated.emit(&"MISS", delta, ACCENT_MARKERS[accent_index])', self.tap)
        self.assertIn("accent_evaluated.emit(classification, delta, ACCENT_MARKERS[accent_index])", self.tap)
        classifier = re.search(
            r"func _classify_delta\(.*?(?=\n\nfunc )",
            self.source,
            re.DOTALL,
        ).group(0)
        self.assertIn("absolute_delta <= PERFECT_WINDOW", classifier)
        self.assertIn("absolute_delta <= GOOD_WINDOW", classifier)
        self.assertIn('return &"EARLY" if delta < 0.0 else &"LATE"', classifier)

    def test_restart_and_seek_rebuild_silently_without_historical_burst(self) -> None:
        process = re.search(
            r"func _process\(.*?(?=\n\nfunc )",
            self.source,
            re.DOTALL,
        ).group(0)
        rebuild = re.search(
            r"func _rebuild_accent_state\(.*?(?=\n\nfunc )",
            self.source,
            re.DOTALL,
        ).group(0)
        self.assertIn("rewind_detected or forward_seek_detected", process)
        self.assertIn("_rebuild_accent_state(playback_time)", process)
        self.assertIn("_consumed_accents.clear()", rebuild)
        self.assertIn("ACCENT_MARKERS[index] + EARLY_LATE_WINDOW", rebuild)
        self.assertNotIn("accent_evaluated.emit", rebuild)

    def test_trace_identifies_expired_opportunity_as_no_input(self) -> None:
        self.assertIn("INPUT=%s", self.trace)
        self.assertIn("_input_source = input_source", self.trace)

    def test_no_synthetic_input_is_generated(self) -> None:
        self.assertNotIn("InputEvent", self.source)
        self.assertNotIn("Input.parse_input_event", self.source)
        self.assertNotIn("tap_detected.emit", self.source)

    def test_flow_and_trusted_runtime_contracts_are_unchanged(self) -> None:
        for path, expected in TRUSTED.items():
            self.assertEqual(digest(path), expected, path)
        flow = FLOW.read_text(encoding="utf-8")
        self.assertIn("const MISS_RETAINED_FRACTION := 0.60", flow)


if __name__ == "__main__":
    unittest.main()
