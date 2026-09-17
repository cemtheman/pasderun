from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_SCENE = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
GENERATED_SCENE = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
CAMERA_HELPER = ROOT / "scenes/gameplay/generated/fork_camera_framing.gd"
CAMERA_RIG = ROOT / "scenes/gameplay/camera_rig.gd"
DEBUG_HELPER = ROOT / "scenes/gameplay/generated/fork_debug_visualization.gd"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
PLAN = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"

TRUSTED_DANCER_SHA256 = "6068ec94ba4d99fa75180226f2d8cdf0a8172c868b9a4851c7214e1ce0b62748"
TRUSTED_PLAN_SHA256 = "6cc084749cc558659016cb5834da0fab8447c155918c16565a35666439ee1fd4"
TRUSTED_GENERATED_SCENE_SHA256 = "2483eb3de87da79b2ad2ae3ccb734ca868898b3009e5861787be1853162ec7d4"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class GeneratedRuntimeSceneTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scene = RUNTIME_SCENE.read_text(encoding="utf-8")
        cls.helper = CAMERA_HELPER.read_text(encoding="utf-8")
        cls.camera_rig = CAMERA_RIG.read_text(encoding="utf-8")
        cls.debug_helper = DEBUG_HELPER.read_text(encoding="utf-8")

    def test_runtime_instances_generated_geometry_without_legacy_level(self) -> None:
        self.assertIn('path="res://scenes/gameplay/generated/graceful_opening_00_30.tscn"', self.scene)
        self.assertRegex(
            self.scene,
            r'\[node name="GeneratedLevel" parent="\."[^\]]*instance=',
        )
        self.assertNotIn('[node name="Level"', self.scene)
        self.assertNotIn('vertical_slice_01.tscn', self.scene)

    def test_runtime_contains_dancer_camera_music_timeline_and_debug(self) -> None:
        for expected in (
            'name="Dancer" type="CharacterBody3D"',
            'name="CameraRig" type="Node3D"',
            'name="Camera3D" type="Camera3D"',
            'name="Music" type="Node"',
            'name="AudioStreamPlayer" type="AudioStreamPlayer"',
            'name="MusicTimeline" type="Node"',
            'name="DebugHUD" type="CanvasLayer"',
        ):
            self.assertIn(expected, self.scene)

    def test_orthographic_camera_framing_is_wider_with_fixed_lookahead(self) -> None:
        camera = re.search(
            r'\[node name="Camera3D".*?(?=\n\[node )',
            self.scene,
            re.DOTALL,
        ).group(0)
        self.assertIn("projection = 1", camera)
        self.assertIn("size = 7.5", camera)
        self.assertIn("0, 2.2, 8", camera)
        self.assertNotIn("fov =", camera)
        self.assertAlmostEqual(7.5 / 6.325, 1.18577, places=4)
        self.assertAlmostEqual(7.5 / 5.5, 1.36364, places=4)
        self.assertIn("look_ahead: float = 1.75", self.camera_rig)
        self.assertIn("target.global_position.x + look_ahead", self.camera_rig)
        landscape_width = 7.5 * (16.0 / 9.0)
        dancer_screen_x = 0.5 - 1.75 / landscape_width
        self.assertGreaterEqual(dancer_screen_x, 0.35)
        self.assertLessEqual(dancer_screen_x, 0.38)

    def test_runtime_resource_paths_exist_and_generated_events_are_preserved(self) -> None:
        resource_paths = re.findall(r'path="res://([^"]+)"', self.scene)
        self.assertTrue(resource_paths)
        for relative_path in resource_paths:
            self.assertTrue((ROOT / relative_path).is_file(), relative_path)
        generated = GENERATED_SCENE.read_text(encoding="utf-8")
        self.assertIn('[node name="Events" type="Node3D"', generated)
        self.assertIn('type="CollisionShape3D"', generated)

    def test_fork_framing_is_scene_derived_not_time_hard_coded(self) -> None:
        self.assertIn('name="ForkFraming"', self.scene)
        self.assertIn('SafeLowerRoute', self.helper)
        self.assertIn('TechnicalRoute', self.helper)
        self.assertIn('ForkStart', self.helper)
        self.assertIn('ForkMerge', self.helper)
        self.assertNotIn('11.5', self.helper)
        self.assertNotIn('46.0', self.helper)

    def test_runtime_only_fork_debug_visualization_is_scene_derived(self) -> None:
        self.assertIn('name="ForkDebugVisualization"', self.scene)
        self.assertIn('SafeLowerRoute', self.debug_helper)
        self.assertIn('TechnicalRoute', self.debug_helper)
        self.assertIn('ForkStart', self.debug_helper)
        self.assertIn('ForkMerge', self.debug_helper)
        self.assertIn('material_override', self.debug_helper)
        self.assertIn('Label3D.new()', self.debug_helper)
        self.assertNotIn('CollisionShape3D', self.debug_helper)

    def test_trusted_controller_plan_and_generated_geometry_are_unchanged(self) -> None:
        self.assertEqual(sha256(DANCER), TRUSTED_DANCER_SHA256)
        self.assertEqual(sha256(PLAN), TRUSTED_PLAN_SHA256)
        self.assertEqual(sha256(GENERATED_SCENE), TRUSTED_GENERATED_SCENE_SHA256)


if __name__ == "__main__":
    unittest.main()
