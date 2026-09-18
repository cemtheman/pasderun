from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"
RUNTIME_120 = ROOT / "scenes/gameplay/generated/graceful_opening_00_120_runtime.tscn"
PLAN = ROOT / "data/geometry/graceful_opening_00_140_bridge.geometry_plan_v0_1.json"
PROJECT = ROOT / "project.godot"


class Phase9GracefulOpeningFullPieceRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.runtime_120 = RUNTIME_120.read_text(encoding="utf-8")
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        cls.project = PROJECT.read_text(encoding="utf-8")
        cls.bridge = cls.plan["prototype_overlays"]["architectural_spans_v1"][0]

    def test_full_piece_runtime_uses_full_bridge_artifacts(self) -> None:
        self.assertIn('name="GracefulOpening0140Runtime"', self.runtime)
        self.assertIn(
            'path="res://scenes/gameplay/generated/graceful_opening_00_140_bridge.tscn"',
            self.runtime,
        )
        self.assertEqual(
            self.runtime.count(
                'geometry_plan_path = "res://data/geometry/graceful_opening_00_140_bridge.geometry_plan_v0_1.json"'
            ),
            3,
        )

    def test_completion_matches_exact_music_end_not_recovery_extent(self) -> None:
        match = re.search(
            r'\[node name="SliceCompletion".*?position = Vector3\(([^,]+),\s*([^,]+),',
            self.runtime,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        completion_x = float(match.group(1))
        completion_y = float(match.group(2))
        self.assertAlmostEqual(completion_x / 4.0, 140.016, places=4)
        self.assertAlmostEqual(completion_y, -2.7499, places=4)
        self.assertLess(completion_x, float(self.plan["playable_world_extent"]["end_x"]))

    def test_final_bridge_is_shared_legato_span(self) -> None:
        self.assertEqual(self.bridge["topology"], "BRIDGE")
        self.assertTrue(self.bridge["shared_route"])
        self.assertEqual(self.bridge["start_time"], 137.753)
        self.assertEqual(self.bridge["end_time"], 140.016)
        self.assertEqual(self.bridge["source_roles"], ["SUSTAIN", "SUSTAIN"])
        self.assertEqual(self.bridge["source_articulation"], "LEGATO")
        self.assertFalse(self.bridge["new_required_actions"])

    def test_bridge_surface_covers_completion_point(self) -> None:
        exact = [
            runway
            for runway in self.plan["surface_plan"]["runway_intervals"]
            if abs(float(runway["start_x"]) - 551.012) <= 1e-4
            and abs(float(runway["end_x"]) - 560.064) <= 1e-4
        ]
        self.assertEqual(len(exact), 1)
        self.assertAlmostEqual(float(exact[0]["surface_y"]), -2.7499, places=4)

    def test_120_to_end_required_action_sequence_is_preserved(self) -> None:
        events = [
            (float(event["source_time"]), str(event["source_class"]))
            for event in self.plan["events"]
            if float(event["source_time"]) > 120.0
        ]
        self.assertEqual(
            events,
            [
                (120.628, "ACCENT_ACTION"),
                (122.5, "ACCENT_ACTION"),
                (128.0, "LARGE_TRAVELLING_LEAP"),
                (135.5, "ACCENT_ACTION"),
            ],
        )

    def test_runtime_includes_collision_aware_mainline_continuity(self) -> None:
        self.assertIn('name="MainlineContinuitySystem"', self.runtime)
        self.assertIn(
            'script = ExtResource("31_mainline_continuity")',
            self.runtime,
        )
        self.assertIn(
            'mainline_material = ExtResource("32_mainline")',
            self.runtime,
        )

    def test_runtime_preserves_skin_body_flow_debug_and_recovery_layers(self) -> None:
        for token in (
            'name="PlatformSkinSystem"',
            'bridge_material = ExtResource("30_bridge")',
            'script = ExtResource("23_choreo")',
            'script = ExtResource("9_flow")',
            'script = ExtResource("21_recovery")',
            'name="DebugHUD"',
            'name="TapTimingDebug"',
            'name="AccentRuntimeTrace"',
            'tap_accents_require_accent_action = true',
        ):
            self.assertIn(token, self.runtime)

    def test_120_runtime_remains_separate_rollback_baseline(self) -> None:
        self.assertIn('name="GracefulOpening0120Runtime"', self.runtime_120)
        self.assertIn(
            'graceful_opening_00_120_topology_v1_1.tscn',
            self.runtime_120,
        )
        self.assertNotIn('graceful_opening_00_140_bridge.tscn', self.runtime_120)

    def test_project_launches_full_piece_runtime(self) -> None:
        self.assertIn(
            'run/main_scene="res://scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"',
            self.project,
        )


if __name__ == "__main__":
    unittest.main()
