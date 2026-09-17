from __future__ import annotations

import hashlib
import re
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scenes/gameplay/spatial_stall_probe.gd"
PARALLAX = ROOT / "scenes/gameplay/parallax_presentation.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
PARALLAX_ASSETS = {
    ROOT / "assets/visuals/parallax/graceful_opening_far_city_v0_1.png":
        "7c298cff10d00f1ef18ddf41959fd4589618fc7e52b4ba7214eea29ef20322f5",
    ROOT / "assets/visuals/parallax/graceful_opening_mid_palace_frame_v0_1.png":
        "0b3db9717e79ff2c00573e15ba23385d414bcab24d324ad30e457e3015fa759d",
    ROOT / "assets/visuals/parallax/graceful_opening_foreground_stage_v0_1.png":
        "91a02340f465bb537c71ac980b7d5f6a056103fca62383db064037eafc99feb8",
}
START_GATE = ROOT / "scenes/gameplay/runtime_start_gate.gd"
FRAMING = ROOT / "scenes/gameplay/generated/fork_camera_framing.gd"
VISUALS = ROOT / "scenes/gameplay/generated/fork_debug_visualization.gd"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
PLAN = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"

TRUSTED = {
    START_GATE: "bda071ca4a89af71b6227f19d9613b8c12bd9cb24f0007ec3274a583e23198ca",
    FRAMING: "8b14a565bd8d1f45189a4b7801855c8159847545a43f1cba276f19a5da2022e1",
    DANCER: "6068ec94ba4d99fa75180226f2d8cdf0a8172c868b9a4851c7214e1ce0b62748",
    PLAN: "6cc084749cc558659016cb5834da0fab8447c155918c16565a35666439ee1fd4",
    GENERATED: "2483eb3de87da79b2ad2ae3ccb734ca868898b3009e5861787be1853162ec7d4",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SpatialStallProbeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.probe = PROBE.read_text(encoding="utf-8")
        cls.parallax = PARALLAX.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.visuals = VISUALS.read_text(encoding="utf-8")

    def test_probe_is_wired_to_only_runtime_diagnostic_nodes(self) -> None:
        self.assertIn('name="SpatialStallProbe" type="Node" parent="."', self.runtime)
        for path in (
            '../RuntimeStartGate',
            '../CameraRig/ForkFraming',
            '../ForkDebugVisualization',
            '../CameraRig/Camera3D/ParallaxPresentation',
            '../DebugHUD/HUDRoot/BottomStatusPanel/SpatialStallProbe',
        ):
            self.assertIn(f'NodePath("{path}")', self.runtime)

    def test_start_gate_owns_first_input(self) -> None:
        self.assertIn("set_process_input(false)", self.probe)
        self.assertIn('start_gate.connect("runtime_started"', self.probe)
        self.assertIn("func _on_runtime_started()", self.probe)
        self.assertIn("set_process_input(true)", self.probe)

    def test_diagnostic_keys_are_consumed(self) -> None:
        self.assertIn("key_event.keycode == KEY_F", self.probe)
        self.assertIn("key_event.keycode == KEY_V", self.probe)
        self.assertIn("key_event.keycode == KEY_B", self.probe)
        handler = re.search(
            r"func _input\(.*?(?=\n\nfunc )",
            self.probe,
            re.DOTALL,
        ).group(0)
        self.assertEqual(handler.count("set_input_as_handled()"), 3)

    def test_framing_toggle_only_changes_framing_processing(self) -> None:
        handler = re.search(
            r"func _set_framing_enabled\(.*?(?=\n\nfunc )",
            self.probe,
            re.DOTALL,
        ).group(0)
        self.assertIn("fork_camera_framing.process_mode", handler)
        self.assertNotIn("fork_debug_visualization", handler)
        self.assertNotIn("camera.size", handler)

    def test_visual_mode_cycle_is_deterministic(self) -> None:
        handler = re.search(
            r"func _cycle_visualization_mode\(.*?(?=\n\nfunc )",
            self.probe,
            re.DOTALL,
        ).group(0)
        self.assertIn("(_visualization_mode + 1) % VISUALIZATION_MODE_COUNT", handler)
        self.assertIn('call("set_diagnostic_mode", _visualization_mode)', handler)
        self.assertNotIn("fork_camera_framing", handler)
        self.assertNotIn(".new()", handler)

    def test_visualization_resources_are_created_once_not_during_mode_switch(self) -> None:
        mode_handler = re.search(
            r"func set_diagnostic_mode\(.*?(?=\n\nfunc )",
            self.visuals,
            re.DOTALL,
        ).group(0)
        self.assertNotIn(".new()", mode_handler)
        self.assertEqual(self.visuals.count("SphereMesh.new()"), 1)
        self.assertEqual(self.visuals.count("Label3D.new()"), 1)

    def test_visualization_render_paths_are_independently_selectable(self) -> None:
        self.assertIn(
            'const MODE_NAMES := ["OFF", "ROUTES", "MARKERS", "LABELS", "ALL"]',
            self.visuals,
        )
        mode_handler = re.search(
            r"func set_diagnostic_mode\(.*?(?=\n\nfunc )",
            self.visuals,
            re.DOTALL,
        ).group(0)
        self.assertIn("_diagnostic_mode == DiagnosticMode.ROUTES", mode_handler)
        self.assertIn("_diagnostic_mode == DiagnosticMode.MARKERS", mode_handler)
        self.assertIn("_diagnostic_mode == DiagnosticMode.LABELS", mode_handler)
        self.assertIn("or _diagnostic_mode == DiagnosticMode.ALL", mode_handler)
        self.assertIn("else _route_original_materials[index]", mode_handler)
        self.assertIn("marker_mesh.visible = show_markers", mode_handler)
        self.assertIn("marker_label.visible = show_labels", mode_handler)

    def test_hud_is_ascii_safe(self) -> None:
        expected = "STALL PROBE FRAMING:ON VISUALS:ALL BG:ON"
        self.assertIn(expected, self.runtime)
        self.assertTrue(all(ord(character) < 128 for character in expected))

    def test_parallax_assets_are_exact_png_sources(self) -> None:
        for asset, expected_hash in PARALLAX_ASSETS.items():
            data = asset.read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
            self.assertEqual(struct.unpack(">II", data[16:24]), (1672, 941))
            self.assertEqual(data[25], 6, f"RGBA required: {asset}")
            self.assertEqual(digest(asset), expected_hash, asset)

    def test_runtime_has_three_collision_free_parallax_quads(self) -> None:
        expected_paths = (
            "graceful_opening_far_city_v0_1.png",
            "graceful_opening_mid_palace_frame_v0_1.png",
            "graceful_opening_foreground_stage_v0_1.png",
        )
        for filename in expected_paths:
            self.assertIn(f'path="res://assets/visuals/parallax/{filename}"', self.runtime)
        self.assertNotIn("graceful_opening_background_v0_1.png", self.runtime)
        self.assertIn(
            '[node name="ParallaxPresentation" type="Node3D" '
            'parent="CameraRig/Camera3D"',
            self.runtime,
        )
        for layer, z_value in (("FarCity", -24), ("MidPalace", -23), ("ForegroundStage", -22)):
            node = re.search(
                rf'\[node name="{layer}".*?(?=\n\[node )',
                self.runtime,
                re.DOTALL,
            ).group(0)
            self.assertIn('type="MeshInstance3D"', node)
            self.assertIn(f"0, 0, {z_value}", node)
            self.assertNotIn("Collision", node)
            self.assertNotIn("script =", node)
        self.assertEqual(self.runtime.count("size = Vector2(17.5, 9.85)"), 3)
        self.assertEqual(self.runtime.count("transparency = 1"), 2)

    def test_parallax_uses_horizontal_gameplay_progress_only(self) -> None:
        self.assertIn(
            "progress_source.global_position.x - _initial_world_x",
            self.parallax,
        )
        self.assertIn("far_factor: float = 0.005", self.parallax)
        self.assertIn("mid_factor: float = 0.010", self.parallax)
        self.assertIn("foreground_factor: float = 0.018", self.parallax)
        self.assertNotIn("position.y", self.parallax)
        self.assertNotIn("global_position =", self.parallax)
        self.assertNotIn("camera", self.parallax.lower())
        self.assertNotIn("timer", self.parallax.lower())

    def test_background_toggle_only_changes_visibility(self) -> None:
        handler = re.search(
            r"func _set_background_enabled\(.*?(?=\n\nfunc )",
            self.probe,
            re.DOTALL,
        ).group(0)
        self.assertIn("parallax_presentation.visible = enabled", handler)
        self.assertNotIn("load(", handler)
        self.assertNotIn("preload(", handler)
        self.assertNotIn("process_mode", handler)
        self.assertNotIn("fork_camera_framing", handler)
        self.assertNotIn("fork_debug_visualization", handler)

    def test_gameplay_geometry_and_existing_helpers_are_unchanged(self) -> None:
        for path, expected in TRUSTED.items():
            self.assertEqual(digest(path), expected, path)


if __name__ == "__main__":
    unittest.main()
