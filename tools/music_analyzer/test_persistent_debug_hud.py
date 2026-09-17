from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HUD = ROOT / "scenes/gameplay/ascii_debug_hud.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
START_GATE = ROOT / "scenes/gameplay/runtime_start_gate.gd"
PROBE = ROOT / "scenes/gameplay/spatial_stall_probe.gd"

TRUSTED = {
    START_GATE: "bda071ca4a89af71b6227f19d9613b8c12bd9cb24f0007ec3274a583e23198ca",
    PROBE: "ba36cdb99f07c538370856c5afc6b0db5254c792a11677161edd8eb369117ace",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PersistentDebugHudTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.hud = HUD.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_h_key_is_owned_by_hud_after_start_gate_only(self) -> None:
        self.assertIn("set_process_input(false)", self.hud)
        self.assertIn('start_gate.connect("runtime_started"', self.hud)
        self.assertIn("func _on_runtime_started()", self.hud)
        self.assertIn("set_process_input(true)", self.hud)
        self.assertIn("key_event.keycode != KEY_H", self.hud)
        self.assertIn("get_viewport().set_input_as_handled()", self.hud)

    def test_hud_defaults_off_and_toggles_one_common_root(self) -> None:
        self.assertIn("hud_root.visible = false", self.hud)
        self.assertIn("hud_root.visible = not hud_root.visible", self.hud)
        input_handler = re.search(
            r"func _input\(.*?(?=\n\nfunc )",
            self.hud,
            re.DOTALL,
        ).group(0)
        self.assertEqual(input_handler.count(".visible"), 2)
        self.assertNotIn("queue_free", input_handler)
        self.assertNotIn(".new()", input_handler)

    def test_scene_has_one_root_and_three_readability_panels(self) -> None:
        self.assertIn('name="HUDRoot" type="Control" parent="DebugHUD"', self.runtime)
        for panel in ("LeftPanel", "RightPanel", "BottomStatusPanel"):
            self.assertIn(f'name="{panel}" type="PanelContainer"', self.runtime)
        self.assertEqual(
            self.runtime.count('theme_override_styles/panel = SubResource("StyleBoxFlat_debug_panel")'),
            3,
        )
        self.assertIn("bg_color = Color(0.02, 0.02, 0.025, 0.42)", self.runtime)

    def test_568_by_320_reference_regions_do_not_overlap(self) -> None:
        self.assertIn("offset_bottom = 270.0", self.runtime)
        self.assertIn("offset_top = -38.0", self.runtime)
        self.assertIn("offset_bottom = 205.0", self.runtime)
        left_bottom = 270.0
        right_bottom = 205.0
        bottom_top = 320.0 - 38.0
        self.assertLess(left_bottom, bottom_top)
        self.assertLess(right_bottom, bottom_top)
        self.assertGreaterEqual(bottom_top - left_bottom, 8.0)

    def test_all_existing_diagnostics_are_preserved_in_regions(self) -> None:
        expected_nodes = (
            "InputDebug",
            "MusicDebug",
            "AccentDebug",
            "FlowDebug",
            "TapTimingDebug",
            "AccentRuntimeTrace",
            "SpatialStallProbe",
        )
        for node in expected_nodes:
            self.assertIn(f'name="{node}" type="Label"', self.runtime)
        self.assertIn('parent="DebugHUD/HUDRoot/LeftPanel/LeftStack"', self.runtime)
        self.assertIn('parent="DebugHUD/HUDRoot/RightPanel"', self.runtime)
        self.assertIn('parent="DebugHUD/HUDRoot/BottomStatusPanel"', self.runtime)

    def test_h_start_gate_and_f_v_b_probe_sources_are_unchanged(self) -> None:
        for path, expected in TRUSTED.items():
            self.assertEqual(digest(path), expected, path)


if __name__ == "__main__":
    unittest.main()
