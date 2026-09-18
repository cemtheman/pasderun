from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (ROOT / "scenes/gameplay/platform_skin_system.gd").read_text(encoding="utf-8")
RUNTIME = (ROOT / "scenes/gameplay/generated/graceful_opening_00_120_runtime.tscn").read_text(encoding="utf-8")
PLAN = (ROOT / "data/geometry/graceful_opening_00_120_topology_v1_1.geometry_plan_v0_1.json").read_text(encoding="utf-8")


class Phase9PlatformSkinSystemTests(unittest.TestCase):
    def test_skin_system_is_presentation_only(self) -> None:
        self.assertIn("material_override = material", SCRIPT)
        self.assertIn("MeshInstance3D.new()", SCRIPT)
        self.assertNotIn("CollisionShape3D.new()", SCRIPT)
        self.assertNotIn("StaticBody3D.new()", SCRIPT)
        self.assertNotIn("global_position =", SCRIPT)

    def test_runtime_wires_skin_system_to_v1_1_plan(self) -> None:
        self.assertIn('name="PlatformSkinSystem"', RUNTIME)
        self.assertIn('script = ExtResource("24_skin")', RUNTIME)
        self.assertIn(
            'geometry_plan_path = "res://data/geometry/graceful_opening_00_120_topology_v1_1.geometry_plan_v0_1.json"',
            RUNTIME,
        )
        self.assertIn('generated_level = NodePath("../GeneratedLevel")', RUNTIME)

    def test_safe_technical_crest_and_staircase_materials_are_distinct(self) -> None:
        expected = {
            "palace_stage_platform_safe.tres": "panel_spacing = 2.4",
            "palace_stage_platform_technical.tres": "panel_spacing = 1.4",
            "palace_stage_platform_crest.tres": "panel_spacing = 4.5",
            "palace_stage_platform_staircase.tres": "panel_spacing = 0.72",
        }
        for filename, token in expected.items():
            material = (ROOT / "assets/materials" / filename).read_text(encoding="utf-8")
            self.assertIn(
                'path="res://assets/materials/palace_stage_platform.gdshader"',
                material,
            )
            self.assertIn(token, material)

    def test_topology_specific_material_selection_exists(self) -> None:
        self.assertIn('const CREST := "CREST"', SCRIPT)
        self.assertIn('const CRESCENDO_STAIRCASE := "CRESCENDO_STAIRCASE"', SCRIPT)
        self.assertIn("return crest_material", SCRIPT)
        self.assertIn("return staircase_material", SCRIPT)
        self.assertIn("return technical_material", SCRIPT)

    def test_fascia_has_no_collision_contract(self) -> None:
        self.assertIn('fascia.name = "PlatformSkinFascia"', SCRIPT)
        self.assertIn("body.add_child(fascia)", SCRIPT)
        self.assertIn("FASCIA_WIDTH_BLEED", SCRIPT)

    def test_plan_still_contains_both_accepted_topologies(self) -> None:
        self.assertIn('"topology": "CREST"', PLAN)
        self.assertIn('"topology": "CRESCENDO_STAIRCASE"', PLAN)


if __name__ == "__main__":
    unittest.main()
