from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "scenes/gameplay/runtime_start_gate.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
TIMELINE = ROOT / "scenes/gameplay/music_timeline.gd"
MUSICALITY = ROOT / "scenes/gameplay/musicality.gd"
FLOW = ROOT / "scenes/gameplay/flow_tracker.gd"
CAMERA = ROOT / "scenes/gameplay/generated/fork_camera_framing.gd"
PLAN = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"

TRUSTED = {
    DANCER: "6068ec94ba4d99fa75180226f2d8cdf0a8172c868b9a4851c7214e1ce0b62748",
    TIMELINE: "605e9605c5a53ec84b862d4ce0b3893802fdfeb36f20dc09b3c67e3a5a183f68",
    MUSICALITY: "d08a1db94883f79aabb48640f0d194fbf70f99c30a8459d504621243d06bff81",
    FLOW: "95ba1f409457ea6a7c0306055348fa4b7df0404423ac2b9c271c3ca0a120954f",
    CAMERA: "8b14a565bd8d1f45189a4b7801855c8159847545a43f1cba276f19a5da2022e1",
    PLAN: "6cc084749cc558659016cb5834da0fab8447c155918c16565a35666439ee1fd4",
    GENERATED: "2483eb3de87da79b2ad2ae3ccb734ca868898b3009e5861787be1853162ec7d4",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class RuntimeStartGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.gate = GATE.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_scene_has_ascii_start_overlay_and_audio_no_longer_autoplays(self) -> None:
        self.assertIn('name="RuntimeStartGate" type="Node"', self.runtime)
        self.assertIn('name="StartGateOverlay" type="CanvasLayer"', self.runtime)
        self.assertIn('text = "TAP TO START"', self.runtime)
        audio = re.search(
            r'\[node name="AudioStreamPlayer".*?(?=\n\[node )',
            self.runtime,
            re.DOTALL,
        ).group(0)
        self.assertNotIn("autoplay = true", audio)

    def test_prestart_disables_movement_music_timing_and_flow(self) -> None:
        for node in (
            "music_root",
            "dancer",
            "flow_tracker",
            "tap_timing_debug",
            "accent_runtime_trace",
        ):
            self.assertIn(f"{node}.process_mode = Node.PROCESS_MODE_DISABLED", self.gate)
        self.assertIn("audio_player.stop()", self.gate)

    def test_touch_mouse_and_keyboard_share_one_gate(self) -> None:
        self.assertIn("event is InputEventScreenTouch", self.gate)
        self.assertIn("event is InputEventMouseButton", self.gate)
        self.assertIn("event is InputEventKey", self.gate)
        self.assertIn("if _started or not _is_valid_start_event(event):", self.gate)

    def test_first_input_starts_audio_at_zero_and_is_consumed(self) -> None:
        self.assertIn("get_viewport().set_input_as_handled()", self.gate)
        self.assertIn("audio_player.play(0.0)", self.gate)
        self.assertIn("call_deferred(\"_enable_dancer_after_start_input\")", self.gate)
        handler = re.search(
            r"func _input\(.*?(?=\n\nfunc )",
            self.gate,
            re.DOTALL,
        ).group(0)
        self.assertNotIn("tap_detected", handler)
        self.assertNotIn("_jump", handler)
        self.assertNotIn("_start_low_transition", handler)

    def test_runtime_systems_resume_without_tuning_or_input_changes(self) -> None:
        for node in (
            "music_root",
            "flow_tracker",
            "tap_timing_debug",
            "accent_runtime_trace",
        ):
            self.assertIn(f"{node}.process_mode = Node.PROCESS_MODE_INHERIT", self.gate)
        self.assertIn("dancer.process_mode = Node.PROCESS_MODE_INHERIT", self.gate)
        self.assertIn("runtime_started.emit()", self.gate)

    def test_gameplay_music_geometry_and_camera_contracts_are_unchanged(self) -> None:
        for path, expected in TRUSTED.items():
            self.assertEqual(digest(path), expected, path)


if __name__ == "__main__":
    unittest.main()
