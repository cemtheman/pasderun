from __future__ import annotations

import hashlib
import re
import struct
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "scenes/gameplay/spatial_stall_probe.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
BACKGROUND = ROOT / "assets/visuals/graceful_opening_background_v0_1.png"
START_GATE = ROOT / "scenes/gameplay/runtime_start_gate.gd"
FRAMING = ROOT / "scenes/gameplay/generated/fork_camera_framing.gd"
VISUALS = ROOT / "scenes/gameplay/generated/fork_debug_visualization.gd"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
PLAN = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"

TRUSTED = {
    START_GATE: "bda071ca4a89af71b6227f19d9613b8c12bd9cb24f0007ec3274a583e23198ca",
    FRAMING: "8b14a565bd8d1f45189a4b7801855c8159847545a43f1cba276f19a5da2022e1",
    VISUALS: "d3f001d98b64169cf41d9a10126399ccd23c57d1dacaec21f8f4327f769a4553",
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
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_probe_is_wired_to_only_runtime_diagnostic_nodes(self) -> None:
        self.assertIn('name="SpatialStallProbe" type="Node" parent="."', self.runtime)
        for path in (
            '../RuntimeStartGate',
            '../CameraRig/ForkFraming',
            '../ForkDebugVisualization',
            '../CameraRig/Camera3D/TemporaryBackground',
            '../DebugHUD/SpatialStallProbe',
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

    def test_visual_toggle_only_changes_debug_visualization(self) -> None:
        handler = re.search(
            r"func _set_visuals_enabled\(.*?(?=\n\nfunc )",
            self.probe,
            re.DOTALL,
        ).group(0)
        self.assertIn("fork_debug_visualization.visible = enabled", handler)
        self.assertIn("fork_debug_visualization.process_mode", handler)
        self.assertNotIn("fork_camera_framing", handler)

    def test_hud_is_ascii_safe(self) -> None:
        expected = "STALL PROBE FRAMING:ON VISUALS:ON BG:ON"
        self.assertIn(expected, self.runtime)
        self.assertTrue(all(ord(character) < 128 for character in expected))

    def test_background_is_static_presentation_only_quad(self) -> None:
        self.assertTrue(BACKGROUND.is_file())
        self.assertEqual(BACKGROUND.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")
        width, height = struct.unpack(">II", BACKGROUND.read_bytes()[16:24])
        self.assertEqual((width, height), (1672, 941))
        self.assertIn(
            'path="res://assets/visuals/graceful_opening_background_v0_1.png"',
            self.runtime,
        )
        self.assertIn('[sub_resource type="QuadMesh" id="QuadMesh_background"]', self.runtime)
        self.assertIn("size = Vector2(15, 8.44)", self.runtime)
        self.assertIn(
            '[node name="TemporaryBackground" type="MeshInstance3D" '
            'parent="CameraRig/Camera3D"]',
            self.runtime,
        )
        background_node = re.search(
            r'\[node name="TemporaryBackground".*?(?=\n\[node )',
            self.runtime,
            re.DOTALL,
        ).group(0)
        self.assertIn("0, 0, -20", background_node)
        self.assertNotIn("script =", background_node)
        self.assertNotIn("Collision", background_node)

    def test_background_toggle_only_changes_visibility(self) -> None:
        handler = re.search(
            r"func _set_background_enabled\(.*?(?=\n\nfunc )",
            self.probe,
            re.DOTALL,
        ).group(0)
        self.assertIn("temporary_background.visible = enabled", handler)
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
