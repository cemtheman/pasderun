from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from render_spatial_geometry import apply_spatial_score, render_spatial_scene


ROOT = Path(__file__).resolve().parents[2]
BASE_PLAN = ROOT / "data/geometry/graceful_opening_00_60.geometry_plan_v0_1.json"
SPATIAL_SCORE = ROOT / "data/geometry/graceful_opening_30_60.spatial_score_v0_1.json"
BASE_SCENE = ROOT / "scenes/gameplay/generated/graceful_opening_00_60.tscn"


class Phase9SpatialGeometryRendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_plan = json.loads(BASE_PLAN.read_text(encoding="utf-8"))
        cls.spatial = json.loads(SPATIAL_SCORE.read_text(encoding="utf-8"))
        cls.base_scene = BASE_SCENE.read_text(encoding="utf-8")
        cls.transformed = apply_spatial_score(cls.base_plan, cls.spatial)
        cls.scene = render_spatial_scene(cls.base_plan, cls.spatial)

    def test_base_plan_and_accepted_scene_are_not_mutated(self) -> None:
        original = copy.deepcopy(self.base_plan)
        apply_spatial_score(self.base_plan, self.spatial)
        self.assertEqual(self.base_plan, original)
        self.assertIn('[node name="GracefulOpening0060" type="Node3D"]', self.base_scene)
        self.assertNotIn("GracefulOpening0060Spatial", self.base_scene)

    def test_event_geometry_is_preserved_exactly(self) -> None:
        self.assertEqual(self.transformed["events"], self.base_plan["events"])
        self.assertEqual(
            self.transformed["surface_plan"]["balance_intervals"],
            self.base_plan["surface_plan"]["balance_intervals"],
        )

    def test_only_runway_coverage_inside_spatial_range_is_replaced(self) -> None:
        start_x = float(self.spatial["world_range"]["start_x"])
        end_x = float(self.spatial["world_range"]["end_x"])

        def clipped_outside(
            intervals: list[dict[str, float]],
        ) -> tuple[list[tuple[float, float, float]], list[tuple[float, float, float]]]:
            before: list[tuple[float, float, float]] = []
            after: list[tuple[float, float, float]] = []
            for interval in intervals:
                left = float(interval["start_x"])
                right = float(interval["end_x"])
                surface_y = float(interval["surface_y"])

                before_end = min(right, start_x)
                if before_end - left > 1e-6:
                    before.append((left, before_end, surface_y))

                after_start = max(left, end_x)
                if right - after_start > 1e-6:
                    after.append((after_start, right, surface_y))
            return before, after

        before_base, after_base = clipped_outside(
            self.base_plan["surface_plan"]["runway_intervals"]
        )
        before_new, after_new = clipped_outside(
            self.transformed["surface_plan"]["runway_intervals"]
        )
        self.assertEqual(before_new, before_base)
        self.assertEqual(after_new, after_base)

        inside = [
            interval for interval in self.transformed["surface_plan"]["runway_intervals"]
            if float(interval["start_x"]) >= start_x
            and float(interval["end_x"]) <= end_x
        ]
        self.assertEqual(len(inside), len(self.spatial["segments"]))
        self.assertEqual(
            [(item["start_x"], item["end_x"], item["surface_y"]) for item in inside],
            [
                (item["start_x"], item["end_x"], item["surface_y"])
                for item in self.spatial["segments"]
            ],
        )

    def test_existing_gap_holes_remain_holes(self) -> None:
        gaps = [
            event["geometry"]
            for event in self.base_plan["events"]
            if 30.0 <= float(event["source_time"]) <= 60.0
            and event["geometry"]["type"].endswith("_GAP")
        ]
        self.assertEqual(len(gaps), 4)

        for interval in self.transformed["surface_plan"]["runway_intervals"]:
            for gap in gaps:
                overlap = min(float(interval["end_x"]), float(gap["end_x"])) - max(
                    float(interval["start_x"]), float(gap["start_x"])
                )
                self.assertLessEqual(overlap, 1e-6)

    def test_spatial_scene_is_deterministic_and_distinct(self) -> None:
        self.assertEqual(
            self.scene,
            render_spatial_scene(self.base_plan, self.spatial),
        )
        self.assertIn(
            '[node name="GracefulOpening0060Spatial" type="Node3D"]',
            self.scene,
        )
        self.assertNotEqual(self.scene, self.base_scene)
        self.assertIn(
            'path="res://assets/materials/palace_stage_platform.tres"',
            self.scene,
        )

    def test_spatial_scene_retains_event_nodes(self) -> None:
        for index, event in enumerate(self.base_plan["events"], start=1):
            marker = f'[node name="Event{index:02d}_{event["source_class"]}" type="Marker3D" parent="Events"]'
            self.assertIn(marker, self.scene)

        self.assertIn('name="AccentZone', self.scene)
        self.assertIn('name="SafeLowerRoute', self.scene)
        self.assertIn('name="BalancePassage', self.scene)

    def test_rendered_runway_count_matches_transformed_plan(self) -> None:
        expected = len(self.transformed["surface_plan"]["runway_intervals"])
        actual = self.scene.count('[node name="Runway')
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
