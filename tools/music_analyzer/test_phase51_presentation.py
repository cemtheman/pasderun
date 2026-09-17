from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
COURSE = ROOT / "scenes/gameplay/generated/continuous_technical_course.tscn"
MATERIAL = ROOT / "assets/materials/palace_stage_platform.tres"
SHADER = ROOT / "assets/materials/palace_stage_platform.gdshader"
ORIENTATION = ROOT / "scenes/gameplay/mobile_orientation_gate.gd"
PROJECT = ROOT / "project.godot"
HUD = ROOT / "scenes/gameplay/ascii_debug_hud.gd"
DEBUG_VISUALS = ROOT / "scenes/gameplay/generated/fork_debug_visualization.gd"
RECOVERY = ROOT / "scenes/gameplay/run_recovery_manager.gd"


class Phase51PresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.generated = GENERATED.read_text(encoding="utf-8")
        cls.course = COURSE.read_text(encoding="utf-8")
        cls.orientation = ORIENTATION.read_text(encoding="utf-8")

    def test_shared_palace_material_is_presentation_only(self) -> None:
        self.assertTrue(MATERIAL.is_file())
        shader = SHADER.read_text(encoding="utf-8")
        for color in ("top_color", "side_color", "trim_color"):
            self.assertIn(color, shader)
        for panel_control in ("panel_spacing", "seam_width", "seam_strength"):
            self.assertIn(panel_control, shader)
        self.assertIn("object_position.x / panel_spacing", shader)
        self.assertIn("mix(side_color.rgb, top_surface, top_mask)", shader)
        self.assertNotIn("TIME", shader)
        for scene in (self.generated, self.course):
            self.assertIn("palace_stage_platform.tres", scene)
            shape_blocks = re.findall(
                r'\[sub_resource type="BoxShape3D".*?(?=\n\[|\Z)',
                scene,
                re.DOTALL,
            )
            self.assertTrue(shape_blocks)
            self.assertTrue(all("material =" not in block for block in shape_blocks))
        self.assertNotIn("CollisionShape3D", shader)
        self.assertNotIn("new()", MATERIAL.read_text(encoding="utf-8"))

    def test_route_debug_override_still_restores_base_material(self) -> None:
        debug = DEBUG_VISUALS.read_text(encoding="utf-8")
        self.assertIn("_route_original_materials.append(mesh.material_override)", debug)
        self.assertIn("_route_original_materials[index]", debug)
        self.assertIn("WEB LABELS OFF", debug)

    def test_hud_defaults_off_without_changing_toggle_key(self) -> None:
        hud = HUD.read_text(encoding="utf-8")
        self.assertIn("hud_root.visible = false", hud)
        self.assertIn("key_event.keycode != KEY_H", hud)
        self.assertIn("hud_root.visible = not hud_root.visible", hud)

    def test_landscape_sensor_and_portrait_fallback_are_wired(self) -> None:
        self.assertIn("window/handheld/orientation=4", PROJECT.read_text(encoding="utf-8"))
        self.assertIn('name="MobileOrientationGate" type="Node"', self.runtime)
        self.assertIn('name="PortraitOrientationOverlay" type="CanvasLayer"', self.runtime)
        self.assertIn("Lütfen cihazınızı yatay çevirin", self.runtime)
        self.assertIn('screen.orientation.lock(\'landscape\')', self.orientation)

    def test_portrait_gate_is_mobile_only_and_pauses_coherently(self) -> None:
        self.assertIn('OS.has_feature("mobile")', self.orientation)
        self.assertIn('OS.has_feature("web") and DisplayServer.is_touchscreen_available()', self.orientation)
        self.assertIn("viewport_size.y > viewport_size.x", self.orientation)
        self.assertIn("get_tree().paused = true", self.orientation)
        self.assertIn("audio_player.stream_paused = true", self.orientation)
        self.assertIn("get_tree().paused = false", self.orientation)
        self.assertIn("audio_player.stream_paused = false", self.orientation)
        self.assertIn("get_viewport().size_changed.connect", self.orientation)
        self.assertNotIn("func _process", self.orientation)

    def test_dead_and_complete_continue_to_freeze_flow(self) -> None:
        recovery = RECOVERY.read_text(encoding="utf-8")
        self.assertGreaterEqual(
            recovery.count("flow_tracker.process_mode = Node.PROCESS_MODE_DISABLED"),
            2,
        )


if __name__ == "__main__":
    unittest.main()
