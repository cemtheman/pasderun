from __future__ import annotations

import hashlib
import json
import math
import unittest
from pathlib import Path

from compile_geometry import (
    DANCER_CAPSULE_HEIGHT,
    FALL_LIMIT_Y,
    GAP_CALIBRATION,
    GROUND_HEIGHT,
    SAFE_HEAD_CLEARANCE,
    RUN_SPEED,
    compile_plan,
    render_scene,
    time_to_x,
)


ROOT = Path(__file__).resolve().parents[2]
DEMANDS_PATH = ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json"
PLAN_PATH = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
SCHEMA_PATH = ROOT / "data/geometry/graceful_opening_geometry_plan_schema_v0_1.json"
SCENE_PATH = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
COMPILE_PATH = ROOT / "tools/music_analyzer/compile_geometry.py"
CAMERA_PATH = ROOT / "scenes/gameplay/camera_rig.gd"
DANCER_PATH = ROOT / "scenes/gameplay/dancer.gd"
VERTICAL_SLICE_PATH = ROOT / "scenes/gameplay/vertical_slice_01.tscn"
DANCER_SHA256 = "6068ec94ba4d99fa75180226f2d8cdf0a8172c868b9a4851c7214e1ce0b62748"


class GeometryCompilerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.demands = json.loads(DEMANDS_PATH.read_text(encoding="utf-8"))
        cls.plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.scene = SCENE_PATH.read_text(encoding="utf-8")
        cls.camera = CAMERA_PATH.read_text(encoding="utf-8")
        cls.vertical_slice = VERTICAL_SLICE_PATH.read_text(encoding="utf-8")
        cls.forks = [event for event in cls.plan["events"] if event["branch"] is not None]

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

    def test_automatic_fork_has_distinct_safe_and_technical_routes(self) -> None:
        self.assertTrue(self.forks)
        self.assertNotIn("11.5", COMPILE_PATH.read_text(encoding="utf-8"))
        for event in self.forks:
            branch = event["branch"]
            safe = branch["routes"]["safe"]
            technical = branch["routes"]["technical"]
            self.assertLess(safe["elevation"], technical["elevation"])
            self.assertEqual(safe["collision_geometry"]["shape"], "BOX")
            self.assertEqual(technical["collision_geometry"]["shape"], "BOX")
            self.assertEqual(branch["split"]["no_jump_destination"], "SAFE")
            self.assertEqual(branch["split"]["jump_destination"], "TECHNICAL")

    def test_safe_head_clearance_uses_actual_capsule_and_platform_dimensions(self) -> None:
        self.assertIn("radius = 0.5", self.vertical_slice)
        self.assertIn("height = 2.0", self.vertical_slice)
        for event in self.forks:
            clearance = event["branch"]["clearance"]
            self.assertEqual(clearance["capsule_height"], DANCER_CAPSULE_HEIGHT)
            self.assertEqual(clearance["platform_thickness"], GROUND_HEIGHT)
            self.assertTrue(clearance["valid"])
            self.assertLess(
                clearance["safe_dancer_top_y"],
                clearance["technical_underside_y"] - SAFE_HEAD_CLEARANCE,
            )

    def test_safe_route_is_continuous_and_non_jump_lands_before_merge(self) -> None:
        for event in self.forks:
            branch = event["branch"]
            safe = branch["routes"]["safe"]
            segments = safe["segments"]
            self.assertEqual(len(segments), 1)
            self.assertTrue(segments[0]["collision"])
            self.assertEqual(segments[0]["start_x"], branch["split"]["x"])
            self.assertEqual(segments[0]["end_x"], branch["merge"]["x"])
            self.assertGreater(safe["descent"]["landing_x"], segments[0]["start_x"])
            self.assertLess(safe["descent"]["landing_x"], segments[0]["end_x"])
            self.assertGreater(safe["descent"]["standing_root_y"], FALL_LIMIT_Y)
            technical_entry_end = branch["routes"]["technical"]["segments"][0]["end_x"]
            self.assertGreater(technical_entry_end, safe["descent"]["landing_x"])

    def test_technical_route_is_continuous_except_intended_gaps(self) -> None:
        for event in self.forks:
            segments = event["branch"]["routes"]["technical"]["segments"]
            for previous, following in zip(segments, segments[1:]):
                self.assertEqual(previous["end_x"], following["start_x"])
            gap_types = [segment["type"] for segment in segments if not segment["collision"]]
            self.assertEqual(gap_types, ["ENTRY_GAP", "MEDIUM_GAP", "DROP_MERGE"])

    def test_jump_trajectory_reaches_technical_route(self) -> None:
        same_height_range = self.plan["controller_calibration"]["same_height_horizontal_range"]
        for event in self.forks:
            branch = event["branch"]
            segments = branch["routes"]["technical"]["segments"]
            entry_gap = segments[0]
            first_runway = segments[1]
            landing_x = branch["split"]["x"] + same_height_range
            self.assertLess(entry_gap["end_x"] - entry_gap["start_x"], same_height_range)
            self.assertGreaterEqual(landing_x, first_runway["start_x"])
            self.assertLessEqual(landing_x, first_runway["end_x"])

    def test_physical_merge_and_downstream_elevation_are_real(self) -> None:
        for event in self.forks:
            branch = event["branch"]
            merge = branch["merge"]
            technical_drop = branch["routes"]["technical"]["segments"][-1]
            self.assertEqual(merge["type"], "TECHNICAL_DROP_TO_SAFE")
            self.assertEqual(technical_drop["end_x"], merge["x"])
            self.assertEqual(technical_drop["to_y"], merge["surface_y"])
            safe_descent = branch["routes"]["safe"]["descent"]
            drop_distance = safe_descent["landing_x"] - safe_descent["start_x"]
            self.assertLess(technical_drop["start_x"] + drop_distance, merge["x"])
            downstream = [
                interval for interval in self.plan["surface_plan"]["runway_intervals"]
                if interval["start_x"] >= merge["x"]
            ]
            self.assertTrue(downstream)
            self.assertTrue(all(item["surface_y"] == merge["surface_y"] for item in downstream))
            downstream_events = [item for item in self.plan["events"] if item["world"]["event_x"] > merge["x"]]
            self.assertTrue(downstream_events)
            self.assertTrue(all(item["world"]["surface_y"] == merge["surface_y"] for item in downstream_events))

    def test_generated_scene_has_aligned_mesh_colliders_and_expected_nodes(self) -> None:
        self.assertIn('type="MeshInstance3D"', self.scene)
        self.assertIn('type="CollisionShape3D"', self.scene)
        self.assertIn('name="BalanceArea" type="Area3D"', self.scene)
        self.assertIn('name="AccentZone', self.scene)
        self.assertIn('name="ForkMerge', self.scene)
        self.assertIn('name="SafeLowerRoute', self.scene)
        self.assertIn('name="TechnicalRoute', self.scene)
        self.assertEqual(self.scene.count('[sub_resource type="BoxMesh"'), self.scene.count('[sub_resource type="BoxShape3D"'))

    def test_camera_follows_y_and_dancer_controller_is_unchanged(self) -> None:
        self.assertIn("desired_x := target.global_position.x + look_ahead", self.camera)
        self.assertIn("desired_y := target.global_position.y + _vertical_offset", self.camera)
        dancer_digest = hashlib.sha256(DANCER_PATH.read_bytes()).hexdigest()
        self.assertEqual(dancer_digest, DANCER_SHA256)

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
