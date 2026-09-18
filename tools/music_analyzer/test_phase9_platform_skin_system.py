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

    def test_fork_debug_is_off_by_default_without_startup_allocation(self) -> None:
        debug_script = (
            ROOT / "scenes/gameplay/generated/fork_debug_visualization.gd"
        ).read_text(encoding="utf-8")
        self.assertIn(
            "var _diagnostic_mode := DiagnosticMode.OFF",
            debug_script,
        )
        self.assertIn("var _initialized := false", debug_script)
        self.assertIn("func _ensure_initialized() -> void:", debug_script)
        ready_start = debug_script.index("func _ready() -> void:")
        init_start = debug_script.index("func _ensure_initialized() -> void:")
        ready_block = debug_script[ready_start:init_start]
        self.assertNotIn("_debug_material(", ready_block)
        self.assertIn(
            "if _diagnostic_mode != DiagnosticMode.OFF:",
            debug_script,
        )
        self.assertNotIn(
            "set_diagnostic_mode(DiagnosticMode.ALL)",
            debug_script,
        )

    def test_v2_crest_uses_one_collisionless_architectural_shell(self) -> None:
        self.assertIn("CrestArchitecturalShell", SCRIPT)
        self.assertIn("Geometry2D.triangulate_polygon", SCRIPT)
        self.assertIn("CREST_UNDERSIDE_SWELL", SCRIPT)
        self.assertIn("_set_collision_visual_hidden(body, true)", SCRIPT)
        self.assertNotIn("CollisionShape3D.new()", SCRIPT)

    def test_v2_staircase_preserves_gaps_with_per_step_riser_shells(self) -> None:
        self.assertIn("TheatricalRiserShell", SCRIPT)
        self.assertIn("TheatricalRiserNosing", SCRIPT)
        self.assertIn("STAIR_RISER_BOTTOM_INSET", SCRIPT)
        self.assertNotIn("STEP_GAP_", SCRIPT)

    def test_v2_1_shell_proportions_are_restrained(self) -> None:
        self.assertIn("const CREST_SHELL_DEPTH := 0.36", SCRIPT)
        self.assertIn("const CREST_UNDERSIDE_SWELL := 0.10", SCRIPT)
        self.assertIn("TheatricalRiserLowerBand", SCRIPT)

    def test_v2_2_staircase_uses_slender_visual_deck_independent_of_collision(self) -> None:
        self.assertIn("const STAIR_VISUAL_THICKNESS := 0.18", SCRIPT)
        self.assertIn("const STAIR_RISER_BOTTOM_INSET := 0.035", SCRIPT)
        self.assertIn("const STAIR_NOSING_HEIGHT := 0.045", SCRIPT)
        self.assertIn("const STAIR_LOWER_BAND_HEIGHT := 0.022", SCRIPT)
        self.assertIn(
            "var bottom_y := top_y - STAIR_VISUAL_THICKNESS",
            SCRIPT,
        )
        self.assertNotIn("STAIR_RISER_EXTRA_DEPTH", SCRIPT)

    def test_soar_uses_collisionless_gallery_shell_without_bridging_gaps(self) -> None:
        self.assertIn('const SOAR := "SOAR"', SCRIPT)
        self.assertIn("SoarGalleryShell", SCRIPT)
        self.assertIn("SOAR_ARCH_RISE", SCRIPT)
        self.assertIn("SOAR_VISUAL_EDGE_DEPTH", SCRIPT)
        self.assertIn("_add_local_soar_nosing(", SCRIPT)
        self.assertIn("_set_collision_visual_hidden(body, true)", SCRIPT)
        self.assertNotIn("CollisionShape3D.new()", SCRIPT)

    def test_bridge_shared_span_has_collisionless_gallery_shell(self) -> None:
        self.assertIn('const BRIDGE := "BRIDGE"', SCRIPT)
        self.assertIn("BridgeGalleryShell", SCRIPT)
        self.assertIn("BridgeGalleryNosing", SCRIPT)
        self.assertIn("architectural_spans_v1", SCRIPT)
        self.assertIn("BRIDGE_ARCH_RISE", SCRIPT)
        self.assertNotIn("CollisionShape3D.new()", SCRIPT)

    def test_palace_deck_family_unifies_safe_soar_and_bridge_proportions(self) -> None:
        self.assertIn("const SAFE_VISUAL_THICKNESS := 0.30", SCRIPT)
        self.assertIn("const SOAR_VISUAL_EDGE_DEPTH := 0.28", SCRIPT)
        self.assertIn("const BRIDGE_VISUAL_EDGE_DEPTH := 0.26", SCRIPT)
        self.assertIn("SafeArchitecturalDeck", SCRIPT)
        self.assertIn("SafeGoldenNosing", SCRIPT)

    def test_balance_and_climax_approach_use_shared_palace_deck_grammar(self) -> None:
        self.assertIn("BalanceArchitecturalDeck", SCRIPT)
        self.assertIn("BalanceGoldenNosing", SCRIPT)
        self.assertIn("ApproachArchitecturalDeck", SCRIPT)
        self.assertIn("ApproachGoldenNosing", SCRIPT)
        self.assertIn("MAINLINE_SHARED_THICKNESS := 0.32", SCRIPT)
        self.assertIn("APPROACH_VISUAL_THICKNESS := 0.30", SCRIPT)

    def test_full_runtime_wires_mainline_material_into_platform_skin_system(self) -> None:
        full_runtime = (
            ROOT / "scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"
        ).read_text(encoding="utf-8")
        self.assertIn('mainline_material = ExtResource("32_mainline")', full_runtime)

    def test_final_recovery_runway_continues_bridge_visual_language(self) -> None:
        self.assertIn("BridgeRecoveryDeck", SCRIPT)
        self.assertIn("BridgeRecoveryNosing", SCRIPT)
        self.assertIn("var recovery_index := runway_index + 1", SCRIPT)

    def test_v2_preserves_golden_nosing_signature(self) -> None:
        self.assertIn("_add_absolute_nosing(", SCRIPT)
        self.assertIn("_add_local_nosing(", SCRIPT)
        self.assertIn("trim_material", SCRIPT)

    def test_debug_routes_can_reveal_hidden_collision_meshes(self) -> None:
        debug_script = (
            ROOT / "scenes/gameplay/generated/fork_debug_visualization.gd"
        ).read_text(encoding="utf-8")
        self.assertIn("_route_original_visibility", debug_script)
        self.assertIn("_route_meshes[index].visible", debug_script)
        self.assertIn("if show_routes", debug_script)

    def test_plan_still_contains_both_accepted_topologies(self) -> None:
        self.assertIn('"topology": "CREST"', PLAN)
        self.assertIn('"topology": "CRESCENDO_STAIRCASE"', PLAN)


if __name__ == "__main__":
    unittest.main()
