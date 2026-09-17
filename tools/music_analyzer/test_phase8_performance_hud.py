from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HUD = ROOT / "scenes/gameplay/ascii_debug_hud.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"


class Phase8PerformanceHudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hud = HUD.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_performance_monitors_are_present(self) -> None:
        for monitor in (
            "Performance.TIME_FPS",
            "Performance.TIME_PROCESS",
            "Performance.TIME_PHYSICS_PROCESS",
            "Performance.MEMORY_STATIC",
            "Performance.RENDER_TOTAL_DRAW_CALLS_IN_FRAME",
        ):
            self.assertIn(monitor, self.hud)

    def test_sampling_is_throttled(self) -> None:
        self.assertIn("PERFORMANCE_SAMPLE_INTERVAL := 0.5", self.hud)
        self.assertIn("_performance_elapsed += delta", self.hud)
        self.assertIn("if _performance_elapsed >= PERFORMANCE_SAMPLE_INTERVAL", self.hud)

    def test_performance_output_is_inside_existing_hud(self) -> None:
        self.assertIn('@export var performance_label: Label', self.hud)
        self.assertIn('name="PerformanceDebug" type="Label"', self.runtime)
        self.assertIn(
            'parent="DebugHUD/HUDRoot/LeftPanel/LeftStack"',
            self.runtime,
        )
        self.assertIn(
            'performance_label = NodePath("HUDRoot/LeftPanel/LeftStack/PerformanceDebug")',
            self.runtime,
        )

    def test_startup_profile_collects_first_five_seconds(self) -> None:
        self.assertIn("STARTUP_PROFILE_DURATION := 5.0", self.hud)
        self.assertIn("_startup_profile_active = true", self.hud)
        self.assertIn("func _sample_startup_performance(delta: float)", self.hud)
        self.assertIn("_startup_profile_elapsed += delta", self.hud)
        self.assertIn(
            "if _startup_profile_elapsed >= STARTUP_PROFILE_DURATION",
            self.hud,
        )

    def test_startup_profile_tracks_worst_case_metrics(self) -> None:
        self.assertIn(
            "_startup_min_fps = minf(_startup_min_fps, fps)",
            self.hud,
        )
        self.assertIn(
            "_startup_max_frame_ms = maxf(_startup_max_frame_ms, frame_ms)",
            self.hud,
        )
        self.assertIn(
            "_startup_max_physics_ms = maxf(_startup_max_physics_ms, physics_ms)",
            self.hud,
        )
        self.assertIn(
            "_startup_max_delta_ms = maxf(_startup_max_delta_ms, delta * 1000.0)",
            self.hud,
        )
        self.assertIn(
            "START 5s MINFPS:%d MAXF:%.1fms MAXP:%.1fms",
            self.hud,
        )

    def test_existing_hud_toggle_contract_remains(self) -> None:
        self.assertIn("key_event.keycode != KEY_H", self.hud)
        self.assertIn("hud_root.visible = not hud_root.visible", self.hud)


if __name__ == "__main__":
    unittest.main()
