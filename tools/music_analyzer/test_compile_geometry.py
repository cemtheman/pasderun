from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from compile_geometry import GAP_CALIBRATION, RUN_SPEED, compile_plan, render_scene, time_to_x


ROOT = Path(__file__).resolve().parents[2]
DEMANDS_PATH = ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json"
PLAN_PATH = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
SCHEMA_PATH = ROOT / "data/geometry/graceful_opening_geometry_plan_schema_v0_1.json"
SCENE_PATH = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"


class GeometryCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.demands = json.loads(DEMANDS_PATH.read_text(encoding="utf-8"))
        cls.plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.scene = SCENE_PATH.read_text(encoding="utf-8")

    def test_version_timebase_and_derived_event_positions(self) -> None:
        self.assertEqual(self.plan["schema_version"], "0.1")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "0.1")
        self.assertEqual(self.plan["timebase"]["run_speed_world_units_per_second"], RUN_SPEED)
        for event in self.plan["events"]:
            self.assertEqual(event["world"]["event_x"], time_to_x(event["source_time"]))

    def test_gap_calibration_is_ordered_and_controller_safe(self) -> None:
        small = GAP_CALIBRATION["SMALL_GAP"]["length"]
        medium = GAP_CALIBRATION["MEDIUM_GAP"]["length"]
        large = GAP_CALIBRATION["LARGE_GAP"]["length"]
        self.assertLess(small, medium)
        self.assertLess(medium, large)
        self.assertLess(large, self.plan["controller_calibration"]["same_height_horizontal_range"])
        self.assertEqual(self.plan["geometry_calibration_status"], "prototype_controller_based")

    def test_required_geometry_and_preparation_recovery_exist(self) -> None:
        geometry_types = {event["geometry"]["type"] for event in self.plan["events"]}
        self.assertIn("BALANCE_PASSAGE", geometry_types)
        self.assertIn("LARGE_GAP", geometry_types)
        self.assertIn("ACCENT_ZONE", geometry_types)
        for event in self.plan["events"]:
            self.assertGreater(event["preparation"]["runway_length"], 0)
            self.assertGreater(event["recovery"]["runway_length"], 0)

    def test_mandatory_cut_intervals_do_not_overlap(self) -> None:
        cuts = []
        for event in self.plan["events"]:
            if event["geometry"]["type"] in {"SMALL_GAP", "MEDIUM_GAP", "LARGE_GAP", "BALANCE_PASSAGE"}:
                cuts.append((event["geometry"]["start_x"], event["geometry"]["end_x"]))
        for (_, previous_end), (next_start, _) in zip(sorted(cuts), sorted(cuts)[1:]):
            self.assertLessEqual(previous_end, next_start)

    def test_automatic_fork_has_safe_technical_and_merge_contract(self) -> None:
        forks = [event for event in self.plan["events"] if event["branch"] is not None]
        self.assertTrue(forks)
        for event in forks:
            branch = event["branch"]
            self.assertEqual(branch["safe_route"]["type"], "RUNWAY")
            self.assertIn(branch["technical_route"]["type"], GAP_CALIBRATION)
            self.assertEqual(branch["safe_route"]["end_x"], branch["merge_x"])
            self.assertEqual(branch["technical_route"]["landing_platform_end_x"], branch["merge_x"])

    def test_generated_scene_has_aligned_mesh_colliders_and_expected_nodes(self) -> None:
        self.assertIn('type="MeshInstance3D"', self.scene)
        self.assertIn('type="CollisionShape3D"', self.scene)
        self.assertIn('name="BalanceArea" type="Area3D"', self.scene)
        self.assertIn('name="AccentZone', self.scene)
        self.assertIn('name="ForkMerge', self.scene)
        self.assertEqual(self.scene.count('[sub_resource type="BoxMesh"'), self.scene.count('[sub_resource type="BoxShape3D"'))

    def test_deterministic_plan_and_scene(self) -> None:
        first = compile_plan(self.demands)
        second = compile_plan(self.demands)
        self.assertEqual(first, second)
        self.assertEqual(first, self.plan)
        self.assertEqual(render_scene(first), render_scene(second))
        self.assertEqual(render_scene(first), self.scene)

    def test_no_non_finite_values_or_grand_jete(self) -> None:
        self.assertNotIn("GRAND_JETE", json.dumps(self.plan))

        def walk(value: object) -> None:
            if isinstance(value, dict):
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
            elif isinstance(value, float):
                self.assertTrue(math.isfinite(value))

        walk(self.plan)


if __name__ == "__main__":
    unittest.main()
