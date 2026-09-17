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

    def test_existing_hud_toggle_contract_remains(self) -> None:
        self.assertIn("key_event.keycode != KEY_H", self.hud)
        self.assertIn("hud_root.visible = not hud_root.visible", self.hud)


if __name__ == "__main__":
    unittest.main()
