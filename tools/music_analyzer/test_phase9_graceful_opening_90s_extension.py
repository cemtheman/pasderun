from __future__ import annotations

import json
import unittest
from pathlib import Path

from build_90_second_extension import (
    BASELINE_END_X,
    build_90_second_extension,
)
from build_climax_fork import render_climax_fork_scene


ROOT = Path(__file__).resolve().parents[2]
DEMANDS = json.loads(
    (ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json").read_text(encoding="utf-8")
)
VISUAL = json.loads(
    (ROOT / "data/music/graceful_opening.visual_score_v0_1.json").read_text(encoding="utf-8")
)
ACCEPTED_60 = json.loads(
    (ROOT / "data/geometry/graceful_opening_00_60_climax_fork.geometry_plan_v0_1.json").read_text(encoding="utf-8")
)


def clipped_prefix(intervals: list[dict[str, object]]) -> list[tuple[float, float, float]]:
    result: list[tuple[float, float, float]] = []
    for interval in intervals:
        left = float(interval["start_x"])
        right = min(float(interval["end_x"]), BASELINE_END_X)
        if left >= BASELINE_END_X or right <= left:
            continue
        result.append((left, right, float(interval["surface_y"])))
    return result


class Phase9GracefulOpening90sExtensionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base_90, cls.spatial, cls.plan = build_90_second_extension(
            DEMANDS,
            VISUAL,
            ACCEPTED_60,
        )
        cls.scene = render_climax_fork_scene(cls.plan)

    def test_accepted_0_to_60_event_contract_is_immutable(self) -> None:
        accepted = [
            event for event in ACCEPTED_60["events"]
            if float(event["source_time"]) <= 60.0
        ]
        actual = [
            event for event in self.plan["events"]
            if float(event["source_time"]) <= 60.0
        ]
        self.assertEqual(actual, accepted)

    def test_accepted_0_to_60_runway_and_ramp_geometry_is_frozen_to_completion(self) -> None:
        self.assertEqual(
            clipped_prefix(self.plan["surface_plan"]["runway_intervals"]),
            clipped_prefix(ACCEPTED_60["surface_plan"]["runway_intervals"]),
        )
        self.assertEqual(
            self.plan["surface_plan"]["ramps"][:len(ACCEPTED_60["surface_plan"]["ramps"])],
            ACCEPTED_60["surface_plan"]["ramps"],
        )

    def test_90_second_base_and_extension_horizons_are_exact(self) -> None:
        self.assertEqual(self.base_90["compiled_time_range"], {"start": 0.0, "end": 90.0})
        self.assertEqual(self.plan["compiled_time_range"], {"start": 0.0, "end": 90.0})
        self.assertEqual(self.plan["playable_world_extent"]["end_x"], 368.0)
        self.assertEqual(self.spatial["time_range"], {"start": 60.0, "end": 90.0})
        self.assertEqual(self.spatial["world_range"], {"start_x": 240.0, "end_x": 360.0})

    def test_60_to_90_required_jump_anchors_are_preserved(self) -> None:
        anchors = [
            (float(anchor["time"]), anchor["interaction"]["candidate_action"])
            for anchor in VISUAL["event_anchors"]
            if 60.0 <= float(anchor["time"]) < 90.0
            and bool(anchor["interaction"]["required"])
        ]
        self.assertEqual(
            anchors,
            [
                (60.604, "JUMP"),
                (68.5, "JUMP"),
                (74.118, "JUMP"),
                (82.75, "JUMP"),
                (87.353, "JUMP"),
            ],
        )
        self.assertEqual(
            [float(lock["time"]) for lock in self.spatial["action_locks"]],
            [60.604, 68.5, 74.118, 82.75, 87.353],
        )

    def test_only_major_extension_climaxes_become_new_forks(self) -> None:
        extension = self.plan["prototype_overlays"]["extension_60_90"]
        self.assertEqual(extension["fork_times"], [68.5, 82.75])
        self.assertFalse(extension["new_required_actions"])

        events = {float(event["source_time"]): event for event in self.plan["events"]}
        self.assertEqual(events[68.5]["geometry"]["type"], "ROUTE_FORK")
        self.assertEqual(events[82.75]["geometry"]["type"], "ROUTE_FORK")
        self.assertEqual(events[60.604]["geometry"]["type"], "SMALL_GAP")
        self.assertEqual(events[74.118]["geometry"]["type"], "SMALL_GAP")
        self.assertEqual(events[87.353]["geometry"]["type"], "SMALL_GAP")

    def test_all_extension_forks_keep_single_input_route_selection(self) -> None:
        for time in (68.5, 82.75):
            event = next(
                event for event in self.plan["events"]
                if float(event["source_time"]) == time
            )
            branch = event["branch"]
            self.assertEqual(branch["split"]["jump_destination"], "TECHNICAL")
            self.assertEqual(branch["split"]["no_jump_destination"], "SAFE")
            self.assertEqual(
                branch["selection"],
                "no jump drops to LOWER SAFE; one climax jump reaches UPPER TECHNICAL",
            )

    def test_scene_contains_four_major_climax_ramps_and_90s_root(self) -> None:
        self.assertIn('name="GracefulOpening0090ClimaxFork"', self.scene)
        for index in range(1, 5):
            self.assertIn(f'name="ClimaxApproachRamp{index:02d}"', self.scene)
        self.assertGreaterEqual(self.scene.count('name="SafeLowerRoute'), 5)
        self.assertGreaterEqual(self.scene.count('name="TechnicalRoute'), 5)

    def test_extension_is_deterministic(self) -> None:
        base_again, spatial_again, plan_again = build_90_second_extension(
            DEMANDS,
            VISUAL,
            ACCEPTED_60,
        )
        self.assertEqual(self.base_90, base_again)
        self.assertEqual(self.spatial, spatial_again)
        self.assertEqual(self.plan, plan_again)
        self.assertEqual(self.scene, render_climax_fork_scene(plan_again))


if __name__ == "__main__":
    unittest.main()
