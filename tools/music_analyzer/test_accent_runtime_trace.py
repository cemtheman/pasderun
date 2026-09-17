from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TRACE = ROOT / "scenes/gameplay/accent_runtime_trace.gd"
MUSICALITY = ROOT / "scenes/gameplay/musicality.gd"
FLOW = ROOT / "scenes/gameplay/flow_tracker.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
TIMELINE = ROOT / "scenes/gameplay/music_timeline.gd"
PLAN = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
COMPILER = ROOT / "tools/music_analyzer/compile_geometry.py"
CAMERA = ROOT / "scenes/gameplay/generated/fork_camera_framing.gd"

TRUSTED = {
    FLOW: "90e1ff56977a8c93198d3d9b1fc932f3edef945b38ad1eb902555f0deb20fb3a",
    DANCER: "6068ec94ba4d99fa75180226f2d8cdf0a8172c868b9a4851c7214e1ce0b62748",
    TIMELINE: "605e9605c5a53ec84b862d4ce0b3893802fdfeb36f20dc09b3c67e3a5a183f68",
    PLAN: "6cc084749cc558659016cb5834da0fab8447c155918c16565a35666439ee1fd4",
    GENERATED: "2ede8fcbd2a7158332c1656459a0e41e12886a8af4c3101576131713ef6ca4e6",
    COMPILER: "8dbd7e00769a83841b859813ba243169c941579a6c6f74dc1fa6b56dfefb0bae",
    CAMERA: "8b14a565bd8d1f45189a4b7801855c8159847545a43f1cba276f19a5da2022e1",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AccentRuntimeTraceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.trace = TRACE.read_text(encoding="utf-8")
        cls.musicality = MUSICALITY.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_runtime_wires_compact_trace_to_real_nodes(self) -> None:
        self.assertIn('path="res://scenes/gameplay/accent_runtime_trace.gd"', self.runtime)
        self.assertIn('name="AccentRuntimeTrace" type="Node" parent="."', self.runtime)
        self.assertIn('musicality = NodePath("../Music/Musicality")', self.runtime)
        self.assertIn('flow_tracker = NodePath("../FlowTracker")', self.runtime)
        self.assertIn('name="AccentRuntimeTrace" type="Label"', self.runtime)

    def test_trace_covers_every_requested_runtime_value(self) -> None:
        for field in (
            "EVAL t=",
            "MARKER=",
            "DELTA=",
            "INPUT=",
            "CLASS=",
            "SIGNAL=",
            "FLOW BEFORE=",
            "FLOW HANDLER=",
            "FLOW NEXT PHYSICS=",
            "HUD FLOW=",
        ):
            self.assertIn(field, self.trace)

    def test_trace_observes_real_signals_and_next_physics_frame(self) -> None:
        self.assertIn('musicality.connect(&"accent_evaluation_started"', self.trace)
        self.assertIn('musicality.connect(&"accent_evaluated"', self.trace)
        self.assertIn('flow_tracker.connect(&"flow_changed"', self.trace)
        self.assertIn("Engine.get_physics_frames() <= _handler_physics_frame", self.trace)
        self.assertIn('call_deferred("_confirm_signal_presence"', self.trace)
        self.assertIn('_signal_status = "NO"', self.trace)

    def test_musicality_diagnostic_signal_does_not_replace_classification(self) -> None:
        self.assertIn("signal accent_evaluation_started", self.musicality)
        self.assertIn("signal accent_evaluated", self.musicality)
        handler = re.search(
            r"func _on_tap_detected\(\).*?(?=\n\nfunc )",
            self.musicality,
            re.DOTALL,
        ).group(0)
        self.assertIn("accent_evaluation_started.emit", handler)
        self.assertIn('&"TAP"', handler)
        self.assertIn('accent_evaluated.emit(&"MISS"', handler)
        self.assertIn("accent_evaluated.emit(classification", handler)

    def test_instrumentation_is_observational_only(self) -> None:
        for forbidden in (
            "_set_flow",
            "MISS_RETAINED_FRACTION",
            "CONTRIBUTIONS",
            "Input.",
            "tap_detected.emit",
            "accent_evaluated.emit",
        ):
            self.assertNotIn(forbidden, self.trace)
        self.assertNotIn("flow_tracker.set", self.trace)

    def test_all_trusted_gameplay_geometry_and_camera_files_are_unchanged(self) -> None:
        for path, expected in TRUSTED.items():
            self.assertEqual(digest(path), expected, path)

    def test_tuning_and_classification_constants_remain_exact(self) -> None:
        self.assertIn("const ACCENT_MARKERS: Array[float] = [18.0, 22.0, 26.0]", self.musicality)
        self.assertIn("const PERFECT_WINDOW := 0.12", self.musicality)
        self.assertIn("const GOOD_WINDOW := 0.28", self.musicality)
        self.assertIn("const EARLY_LATE_WINDOW := 0.50", self.musicality)
        flow = FLOW.read_text(encoding="utf-8")
        self.assertIn("const MISS_RETAINED_FRACTION := 0.60", flow)


if __name__ == "__main__":
    unittest.main()
