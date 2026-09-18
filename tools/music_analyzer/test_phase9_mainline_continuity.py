from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = (
    ROOT / "scenes/gameplay/mainline_continuity_system.gd"
).read_text(encoding="utf-8")
RUNTIME = (
    ROOT / "scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"
).read_text(encoding="utf-8")


class Phase9MainlineContinuityTests(unittest.TestCase):
    def test_mainline_smoothing_is_collision_aware(self) -> None:
        self.assertIn("StaticBody3D.new()", SCRIPT)
        self.assertIn("CollisionShape3D.new()", SCRIPT)
        self.assertIn("BoxShape3D.new()", SCRIPT)
        self.assertIn('collision.set_deferred("disabled", true)', SCRIPT)

    def test_small_passive_height_changes_are_the_only_smoothing_target(self) -> None:
        self.assertIn("const MAX_SMOOTH_DELTA := 0.20", SCRIPT)
        self.assertIn("const GROUND_HEIGHT := 0.5", SCRIPT)
        self.assertIn("contiguous and smooth_delta", SCRIPT)

    def test_ramp_surface_and_collision_share_the_same_transform(self) -> None:
        self.assertIn("var angle := atan2(dy, dx)", SCRIPT)
        self.assertIn("body.rotation = Vector3(0.0, 0.0, angle)", SCRIPT)
        self.assertIn(
            "shape_resource.size = Vector3(length, GROUND_HEIGHT, GROUND_WIDTH)",
            SCRIPT,
        )

    def test_mainline_visual_deck_is_thinner_than_collision_but_top_aligned(self) -> None:
        self.assertIn("const MAINLINE_VISUAL_THICKNESS := 0.32", SCRIPT)
        self.assertIn("MainlineArchitecturalDeck", SCRIPT)
        self.assertIn(
            "base_box.size.y * 0.5 - MAINLINE_VISUAL_THICKNESS * 0.5",
            SCRIPT,
        )
        self.assertIn(
            "GROUND_HEIGHT * 0.5 - MAINLINE_VISUAL_THICKNESS * 0.5",
            SCRIPT,
        )

    def test_mainline_keeps_architectural_mass_and_golden_edge(self) -> None:
        self.assertIn(
            "shape_resource.size = Vector3(length, GROUND_HEIGHT, GROUND_WIDTH)",
            SCRIPT,
        )
        self.assertIn("MAINLINE_VISUAL_THICKNESS", SCRIPT)
        self.assertIn("MainlineGoldenNosing", SCRIPT)
        self.assertIn("mainline_material", SCRIPT)
        self.assertIn("trim_material", SCRIPT)

    def test_bridge_is_excluded_from_mainline_replacement(self) -> None:
        self.assertIn("_excluded_architectural_spans", SCRIPT)
        self.assertIn('String(span.get("topology", "")) != BRIDGE', SCRIPT)

    def test_mainline_excludes_final_bridge_recovery_extent(self) -> None:
        self.assertIn('plan.get("playable_world_extent", {})', SCRIPT)
        self.assertIn("exclusion_end = extent_end", SCRIPT)

    def test_full_runtime_wires_continuity_before_platform_skinning(self) -> None:
        continuity = RUNTIME.index('[node name="MainlineContinuitySystem"')
        skin = RUNTIME.index('[node name="PlatformSkinSystem"')
        self.assertGreaterEqual(continuity, 0)
        self.assertGreater(skin, continuity)
        self.assertIn(
            'path="res://assets/materials/palace_stage_platform_mainline.tres"',
            RUNTIME,
        )


if __name__ == "__main__":
    unittest.main()
