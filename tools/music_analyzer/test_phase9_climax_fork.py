from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from build_climax_fork import (
    MAX_APPROACH_SLOPE_DEGREES,
    build_climax_fork_plan,
    render_climax_fork_scene,
)


ROOT = Path(__file__).resolve().parents[2]
BASE_PLAN = json.loads(
    (ROOT / "data/geometry/graceful_opening_00_60.geometry_plan_v0_1.json").read_text(encoding="utf-8")
)
SPATIAL = json.loads(
    (ROOT / "data/geometry/graceful_opening_30_60.spatial_score_v0_1.json").read_text(encoding="utf-8")
)
VISUAL = json.loads(
    (ROOT / "data/music/graceful_opening.visual_score_v0_1.json").read_text(encoding="utf-8")
)
FLOW = (ROOT / "scenes/gameplay/flow_tracker.gd").read_text(encoding="utf-8")


class Phase9ClimaxForkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = build_climax_fork_plan(BASE_PLAN, SPATIAL, VISUAL)
        cls.scene = render_climax_fork_scene(cls.plan)
        cls.overlay = cls.plan["prototype_overlays"]["climax_fork_v0_1"]
        cls.event = next(event for event in cls.plan["events"] if event["source_time"] == 53.0)

    def test_strongest_climax_is_selected_without_adding_input(self) -> None:
        self.assertEqual(self.overlay["target_time"], 53.0)
        self.assertEqual(self.overlay["climax_peak"], 1.0)
        self.assertEqual(self.overlay["required_action"], "JUMP")
        self.assertFalse(self.overlay["new_required_actions"])

    def test_build_approach_is_single_traversable_ramp(self) -> None:
        ramps = self.plan["surface_plan"]["ramps"]
        self.assertEqual(len(ramps), 1)
        ramp = ramps[0]
        self.assertLess(ramp["start_surface_y"], ramp["end_surface_y"])
        self.assertEqual(ramp["end_x"], self.event["branch"]["split"]["x"])
        self.assertLessEqual(self.overlay["approach_slope_degrees"], MAX_APPROACH_SLOPE_DEGREES)

    def test_climax_jump_alone_selects_upper_technical_route(self) -> None:
        branch = self.event["branch"]
        technical = branch["routes"]["technical"]
        gaps = [
            segment for segment in technical["segments"]
            if not segment["collision"] and str(segment["type"]).endswith("_GAP")
        ]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["type"], "LARGE_GAP")
        self.assertEqual(gaps[0]["start_x"], branch["split"]["x"])
        self.assertLess(gaps[0]["start_x"], self.event["world"]["event_x"])
        self.assertGreater(gaps[0]["end_x"], self.event["world"]["event_x"])
        self.assertLess(
            gaps[0]["end_x"] - gaps[0]["start_x"],
            self.plan["controller_calibration"]["same_height_horizontal_range"],
        )
        self.assertEqual(branch["split"]["no_jump_destination"], "SAFE")
        self.assertEqual(branch["split"]["jump_destination"], "TECHNICAL")

    def test_safe_route_and_clearance_remain_physically_valid(self) -> None:
        branch = self.event["branch"]
        safe = branch["routes"]["safe"]
        self.assertLess(safe["elevation"], branch["routes"]["technical"]["elevation"])
        self.assertGreater(
            safe["descent"]["standing_root_y"],
            self.plan["controller_calibration"]["fall_limit_y"],
        )
        self.assertTrue(branch["clearance"]["valid"])
        self.assertLess(safe["descent"]["landing_x"], branch["merge"]["x"])

    def test_overlay_removes_flat_runway_under_ramp_and_fork(self) -> None:
        ramp = self.plan["surface_plan"]["ramps"][0]
        merge_x = self.event["branch"]["merge"]["x"]
        for interval in self.plan["surface_plan"]["runway_intervals"]:
            overlap = min(float(interval["end_x"]), merge_x) - max(
                float(interval["start_x"]), float(ramp["start_x"])
            )
            self.assertLessEqual(overlap, 1e-6)

    def test_ramp_updates_approach_event_surface(self) -> None:
        accent = next(event for event in self.plan["events"] if event["source_time"] == 50.62)
        ramp = self.plan["surface_plan"]["ramps"][0]
        progress = (
            (accent["world"]["event_x"] - ramp["start_x"])
            / (ramp["end_x"] - ramp["start_x"])
        )
        expected = ramp["start_surface_y"] + (
            ramp["end_surface_y"] - ramp["start_surface_y"]
        ) * progress
        self.assertAlmostEqual(accent["world"]["surface_y"], expected, places=3)

    def test_scene_contains_ramp_both_routes_and_fork_markers(self) -> None:
        self.assertIn('name="GracefulOpening0060ClimaxFork"', self.scene)
        self.assertIn('name="ClimaxApproachRamp01"', self.scene)
        self.assertIn('name="SafeLowerRoute', self.scene)
        self.assertIn('name="TechnicalRoute', self.scene)
        self.assertIn('name="ForkStart', self.scene)
        self.assertIn('name="ForkMerge', self.scene)
        self.assertIn('rotation = Vector3(0, 0, ', self.scene)

    def test_scene_is_deterministic(self) -> None:
        again = build_climax_fork_plan(BASE_PLAN, SPATIAL, VISUAL)
        self.assertEqual(self.plan, again)
        self.assertEqual(self.scene, render_climax_fork_scene(again))

    def test_flow_tracker_accepts_old_and_new_fork_gap_shapes(self) -> None:
        self.assertIn("func _find_technical_gap", FLOW)
        self.assertIn('segment_type == "ENTRY_GAP"', FLOW)
        self.assertIn('segment_type.ends_with("_GAP")', FLOW)
        self.assertIn('event["route"] == &""', FLOW)
        self.assertIn('event["gap_airborne"] = true', FLOW)


if __name__ == "__main__":
    unittest.main()
