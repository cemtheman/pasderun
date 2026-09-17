from __future__ import annotations

import json
import unittest
from pathlib import Path

from compile_geometry import (
    FALL_LIMIT_Y,
    RUN_SPEED,
    compile_plan,
    render_scene,
)


ROOT = Path(__file__).resolve().parents[2]
DEMANDS_PATH = ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json"
BASE_PLAN_PATH = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
BASE_SCENE_PATH = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
SCHEMA_PATH = ROOT / "data/geometry/graceful_opening_geometry_plan_schema_v0_1.json"


class Phase9GracefulOpening60sGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.demands = json.loads(DEMANDS_PATH.read_text(encoding="utf-8"))
        cls.base_plan = json.loads(BASE_PLAN_PATH.read_text(encoding="utf-8"))
        cls.base_scene = BASE_SCENE_PATH.read_text(encoding="utf-8")
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_default_30_second_contract_remains_byte_equivalent_at_scene_level(self) -> None:
        plan = compile_plan(self.demands)
        self.assertEqual(plan, self.base_plan)
        self.assertEqual(render_scene(plan), self.base_scene)

    def test_60_second_compile_extends_music_derived_geometry(self) -> None:
        plan = compile_plan(self.demands, 60.0)
        self.assertEqual(plan["compiled_time_range"], {"start": 0.0, "end": 60.0})
        self.assertEqual(plan["playable_world_extent"]["end_x"], 60.0 * RUN_SPEED + 8.0)
        event_times = [event["source_time"] for event in plan["events"]]
        self.assertTrue(any(time > 30.0 for time in event_times))
        self.assertIn(56.889, event_times)
        self.assertTrue(all(time <= 60.0 for time in event_times))

    def test_second_descent_is_suppressed_when_it_would_cross_fall_limit(self) -> None:
        plan = compile_plan(self.demands, 60.0)
        forks = [event for event in plan["events"] if event["branch"] is not None]
        fork_times = [event["source_time"] for event in forks]
        self.assertIn(11.5, fork_times)
        self.assertNotIn(32.25, fork_times)

        event_32 = next(event for event in plan["events"] if event["source_time"] == 32.25)
        self.assertEqual(event_32["geometry"]["type"], "LARGE_GAP")

        for event in forks:
            standing_root_y = event["branch"]["routes"]["safe"]["descent"]["standing_root_y"]
            self.assertGreater(standing_root_y, FALL_LIMIT_Y)

    def test_60_second_scene_is_deterministic_and_distinct(self) -> None:
        first = compile_plan(self.demands, 60.0)
        second = compile_plan(self.demands, 60.0)
        self.assertEqual(first, second)
        scene = render_scene(first)
        self.assertEqual(scene, render_scene(second))
        self.assertIn('[node name="GracefulOpening0060" type="Node3D"]', scene)
        self.assertNotEqual(scene, self.base_scene)

    def test_geometry_schema_accepts_phase9_event_horizon(self) -> None:
        source_time = self.schema["properties"]["events"]["items"]["properties"]["source_time"]
        self.assertGreaterEqual(source_time["maximum"], 60)


if __name__ == "__main__":
    unittest.main()
