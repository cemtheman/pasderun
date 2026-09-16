from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "project.godot"
EXPORT_PRESETS = ROOT / "export_presets.cfg"
RUNTIME_SCENE = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
VERCEL = ROOT / "vercel.json"

EXPECTED_MAIN_SCENE = (
    'run/main_scene="res://scenes/gameplay/generated/'
    'graceful_opening_00_30_runtime.tscn"'
)


class WebLaunchConfigTests(unittest.TestCase):
    def test_project_launches_generated_runtime_scene(self) -> None:
        project = PROJECT.read_text(encoding="utf-8")
        runtime_header = RUNTIME_SCENE.read_text(encoding="utf-8").splitlines()[0]
        runtime_uid = re.search(r'uid="([^"]+)"', runtime_header).group(1)
        self.assertTrue(
            EXPECTED_MAIN_SCENE in project
            or f'run/main_scene="{runtime_uid}"' in project
        )
        self.assertNotIn('run/main_scene="uid://blf6l5vi6n1lp"', project)
        self.assertTrue(RUNTIME_SCENE.is_file())

    def test_web_export_target_remains_build_web(self) -> None:
        presets = EXPORT_PRESETS.read_text(encoding="utf-8")
        self.assertIn('name="Web"', presets)
        self.assertIn('platform="Web"', presets)
        self.assertIn('export_path="build/web/index.html"', presets)

    def test_vercel_is_explicit_static_output_not_python(self) -> None:
        config = json.loads(VERCEL.read_text(encoding="utf-8"))
        self.assertIsNone(config["framework"])
        self.assertEqual(config["installCommand"], "")
        self.assertEqual(config["outputDirectory"], "build/web")
        self.assertNotIn("python", config["buildCommand"].lower())
        self.assertNotIn("api", config)
        self.assertNotIn("functions", config)


if __name__ == "__main__":
    unittest.main()
