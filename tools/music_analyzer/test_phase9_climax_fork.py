from __future__ import annotations

import json
import unittest
from pathlib import Path

from build_climax_fork import (
    ACCENT_BODY_CLEARANCE_SECONDS,
    MAJOR_CLIMAX_MINIMUM,
    MAX_APPROACH_SLOPE_DEGREES,
    RUN_SPEED,
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
        cls.overlays = cls.plan["prototype_overlays"]["climax_forks_v0_2"]
        cls.events = {
            float(event["source_time"]): event
            for event in cls.plan["events"]
        }

    def test_only_major_climaxes_are_promoted_without_adding_input(self) -> None:
        self.assertEqual([item["target_time"] for item in self.overlays], [36.25, 53.0])
        self.assertTrue(all(item["climax_peak"] >= MAJOR_CLIMAX_MINIMUM for item in self.overlays))
        self.assertTrue(all(item["required_action"] == "JUMP" for item in self.overlays))
        self.assertTrue(all(not item["new_required_actions"] for item in self.overlays))
        self.assertEqual(self.events[32.25]["geometry"]["type"], "LARGE_GAP")
        self.assertEqual(self.events[42.5]["geometry"]["type"], "LARGE_GAP")

    def test_each_major_climax_has_a_non_overlapping_traversable_ramp(self) -> None:
        ramps = self.plan["surface_plan"]["ramps"]
        self.assertEqual(len(ramps), 2)
        previous_merge = -float("inf")
        for overlay, ramp in zip(self.overlays, ramps):
            event = self.events[float(overlay["target_time"])]
            self.assertLess(ramp["start_surface_y"], ramp["end_surface_y"])
            self.assertEqual(ramp["end_x"], event["branch"]["split"]["x"])
            self.assertLessEqual(
                overlay["approach_slope_degrees"],
                MAX_APPROACH_SLOPE_DEGREES,
            )
            self.assertGreaterEqual(ramp["start_x"], previous_merge)
            previous_merge = overlay["merge_x"]

    def test_each_climax_jump_alone_selects_upper_technical_route(self) -> None:
        for overlay in self.overlays:
            event = self.events[float(overlay["target_time"])]
            branch = event["branch"]
            technical = branch["routes"]["technical"]
            gaps = [
                segment for segment in technical["segments"]
                if not segment["collision"] and str(segment["type"]).endswith("_GAP")
            ]
            self.assertEqual(len(gaps), 1)
            self.assertEqual(gaps[0]["type"], "LARGE_GAP")
            self.assertEqual(gaps[0]["start_x"], branch["split"]["x"])
            self.assertLess(gaps[0]["start_x"], event["world"]["event_x"])
            self.assertGreater(gaps[0]["end_x"], event["world"]["event_x"])
            self.assertLess(
                gaps[0]["end_x"] - gaps[0]["start_x"],
                self.plan["controller_calibration"]["same_height_horizontal_range"],
            )
            self.assertEqual(branch["split"]["no_jump_destination"], "SAFE")
            self.assertEqual(branch["split"]["jump_destination"], "TECHNICAL")

    def test_safe_routes_and_clearance_remain_physically_valid(self) -> None:
        for overlay in self.overlays:
            event = self.events[float(overlay["target_time"])]
            branch = event["branch"]
            safe = branch["routes"]["safe"]
            self.assertLess(safe["elevation"], branch["routes"]["technical"]["elevation"])
            self.assertGreater(
                safe["descent"]["standing_root_y"],
                self.plan["controller_calibration"]["fall_limit_y"],
            )
            self.assertTrue(branch["clearance"]["valid"])
            self.assertLess(safe["descent"]["landing_x"], branch["merge"]["x"])

    def test_36s_recovery_keeps_37593_tap_on_upper_runway(self) -> None:
        event = self.events[36.25]
        accent = self.events[37.593]
        drop_start = float(event["branch"]["merge"]["drop_start_x"])
        required_clear_x = float(accent["world"]["event_x"]) + RUN_SPEED * ACCENT_BODY_CLEARANCE_SECONDS
        self.assertGreaterEqual(drop_start, required_clear_x - 1e-4)
        self.assertEqual(accent["source_class"], "ACCENT_ACTION")

    def test_53s_accepted_prototype_remains_strongest_alias(self) -> None:
        alias = self.plan["prototype_overlays"]["climax_fork_v0_1"]
        self.assertEqual(alias["target_time"], 53.0)
        self.assertEqual(alias["climax_peak"], 1.0)
        self.assertEqual(self.events[53.0]["branch"]["split"]["jump_destination"], "TECHNICAL")

    def test_overlay_removes_flat_runway_under_both_ramps_and_forks(self) -> None:
        for overlay in self.overlays:
            ramp = overlay["approach_ramp"]
            merge_x = overlay["merge_x"]
            for interval in self.plan["surface_plan"]["runway_intervals"]:
                overlap = min(float(interval["end_x"]), merge_x) - max(
                    float(interval["start_x"]), float(ramp["start_x"])
                )
                self.assertLessEqual(overlap, 1e-6)

    def test_scene_contains_two_ramps_and_all_fork_routes(self) -> None:
        self.assertIn('name="GracefulOpening0060ClimaxFork"', self.scene)
        self.assertIn('name="ClimaxApproachRamp01"', self.scene)
        self.assertIn('name="ClimaxApproachRamp02"', self.scene)
        self.assertGreaterEqual(self.scene.count('name="SafeLowerRoute'), 3)
        self.assertGreaterEqual(self.scene.count('name="TechnicalRoute'), 3)
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
