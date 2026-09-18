from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FORK = (ROOT / "scenes/gameplay/generated/fork_debug_visualization.gd").read_text(encoding="utf-8")
HUD = (ROOT / "scenes/gameplay/ascii_debug_hud.gd").read_text(encoding="utf-8")
TAP = (ROOT / "scenes/gameplay/tap_timing_debug.gd").read_text(encoding="utf-8")
EXPORT = (ROOT / "export_presets.cfg").read_text(encoding="utf-8")


class Phase9WebStartupDietTests(unittest.TestCase):
    def test_fork_diagnostics_allocate_only_after_explicit_enable(self) -> None:
        ready_start = FORK.index("func _ready() -> void:")
        init_start = FORK.index("func _ensure_initialized() -> void:")
        ready_block = FORK[ready_start:init_start]
        self.assertNotIn("StandardMaterial3D.new()", ready_block)
        self.assertNotIn("MeshInstance3D.new()", ready_block)
        self.assertNotIn("_add_marker(", ready_block)
        self.assertIn("var _initialized := false", FORK)
        self.assertIn("if _diagnostic_mode != DiagnosticMode.OFF:", FORK)
        self.assertIn("_ensure_initialized()", FORK)

    def test_hidden_debug_hud_skips_presentation_work(self) -> None:
        ready_start = HUD.index("func _ready() -> void:")
        started_start = HUD.index("func _on_runtime_started() -> void:")
        ready_block = HUD[ready_start:started_start]
        self.assertNotIn("_update_performance_label()", ready_block)
        self.assertNotIn("_sanitize_labels(self)", ready_block)
        self.assertIn("if not hud_root.visible:", HUD)
        self.assertIn("return", HUD[HUD.index("if not hud_root.visible:"):])
        self.assertIn("if hud_root.visible:", HUD)

    def test_web_export_prunes_only_known_obsolete_resources(self) -> None:
        self.assertIn('name="Web"', EXPORT)
        self.assertIn('export_filter="exclude"', EXPORT)
        self.assertIn(
            '"res://assets/visuals/graceful_opening_background_v0_1.png"',
            EXPORT,
        )
        self.assertIn(
            '"res://scenes/gameplay/generated/graceful_opening_00_120_runtime.tscn"',
            EXPORT,
        )
        self.assertNotIn(
            '"res://scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"',
            EXPORT.split("[preset.1]")[0],
        )
        self.assertNotIn(
            '"res://scenes/gameplay/generated/graceful_opening_00_140_bridge.tscn"',
            EXPORT.split("[preset.1]")[0],
        )

    def test_hidden_tap_debug_skips_cue_rendering(self) -> None:
        process_start = TAP.index("func _process(_delta: float) -> void:")
        update_start = TAP.index("func _update_cue(playback_time: float) -> void:")
        process_block = TAP[process_start:update_start]
        self.assertIn("if not debug_label.is_visible_in_tree():", process_block)
        hidden_guard = process_block.index("if not debug_label.is_visible_in_tree():")
        return_pos = process_block.index("return", hidden_guard)
        update_pos = process_block.index("_update_cue(playback_time)")
        self.assertLess(return_pos, update_pos)


if __name__ == "__main__":
    unittest.main()
