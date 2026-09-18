from __future__ import annotations

import json
import unittest
from pathlib import Path

from build_120_second_extension import (
    BASELINE_END_X,
    STAIR_GAP_LENGTH,
    STAIR_PLATFORM_LENGTH,
    STAIR_STEP_RISE,
    build_120_second_extension,
)
from build_climax_fork import render_climax_fork_scene
from fork_topology_vocabulary import (
    CRESCENDO_STAIRCASE,
    SOAR,
    TIER_CONTRACT,
    classify_topology,
)


ROOT = Path(__file__).resolve().parents[2]
DEMANDS = json.loads(
    (ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json").read_text(encoding="utf-8")
)
VISUAL = json.loads(
    (ROOT / "data/music/graceful_opening.visual_score_v0_1.json").read_text(encoding="utf-8")
)
ACCEPTED_90 = json.loads(
    (ROOT / "data/geometry/graceful_opening_00_90_climax_fork.geometry_plan_v0_1.json").read_text(encoding="utf-8")
)
FLOW = (ROOT / "scenes/gameplay/flow_tracker.gd").read_text(encoding="utf-8")
COMPILER = (ROOT / "tools/music_analyzer/compile_geometry.py").read_text(encoding="utf-8")


class Phase9ForkTopologyVocabularyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base, cls.spatial, cls.plan = build_120_second_extension(
            DEMANDS,
            VISUAL,
            ACCEPTED_90,
        )
        cls.scene = render_climax_fork_scene(cls.plan)
        cls.events = {
            float(event["source_time"]): event
            for event in cls.plan["events"]
        }

    def test_vocabulary_declares_safe_technical_and_future_virtuoso_tiers(self) -> None:
        self.assertEqual(TIER_CONTRACT["TECHNICAL"]["failure_policy"], "FAIL_DOWN_TO_SAFE")
        self.assertEqual(
            TIER_CONTRACT["VIRTUOSO"]["failure_policy"],
            "FAIL_DOWN_TO_TECHNICAL_OR_SAFE",
        )

    def test_1025_major_climax_is_classified_as_crescendo_staircase(self) -> None:
        anchor = next(
            anchor for anchor in VISUAL["event_anchors"]
            if float(anchor["time"]) == 102.5
        )
        self.assertEqual(classify_topology(VISUAL, anchor), CRESCENDO_STAIRCASE)

        anchor_98 = next(
            anchor for anchor in VISUAL["event_anchors"]
            if float(anchor["time"]) == 98.5
        )
        self.assertIsNone(classify_topology(VISUAL, anchor_98))

        anchor_68 = next(
            anchor for anchor in VISUAL["event_anchors"]
            if float(anchor["time"]) == 68.5
        )
        self.assertEqual(classify_topology(VISUAL, anchor_68), SOAR)

    def test_accepted_0_to_90_event_contract_is_immutable(self) -> None:
        expected = [
            event for event in ACCEPTED_90["events"]
            if float(event["source_time"]) <= 90.0
        ]
        actual = [
            event for event in self.plan["events"]
            if float(event["source_time"]) <= 90.0
        ]
        self.assertEqual(actual, expected)

    def test_accepted_0_to_90_runways_and_ramps_are_frozen(self) -> None:
        expected = [
            interval for interval in ACCEPTED_90["surface_plan"]["runway_intervals"]
            if float(interval["start_x"]) < BASELINE_END_X
        ]
        actual = [
            interval for interval in self.plan["surface_plan"]["runway_intervals"]
            if float(interval["start_x"]) < BASELINE_END_X
        ]
        self.assertEqual(actual, expected)
        self.assertEqual(
            self.plan["surface_plan"]["ramps"][:len(ACCEPTED_90["surface_plan"]["ramps"])],
            ACCEPTED_90["surface_plan"]["ramps"],
        )

    def test_staircase_uses_narrow_rising_steps_with_small_fail_down_gaps(self) -> None:
        event = self.events[102.5]
        self.assertEqual(event["branch"]["topology"], CRESCENDO_STAIRCASE)
        technical = event["branch"]["routes"]["technical"]
        steps = [
            segment for segment in technical["segments"]
            if str(segment["type"]).startswith("STAIR_STEP_")
        ]
        gaps = [
            segment for segment in technical["segments"]
            if str(segment["type"]).startswith("STEP_GAP_")
        ]
        self.assertEqual(len(steps), 4)
        self.assertEqual(len(gaps), 3)
        self.assertTrue(all(
            abs(float(step["end_x"]) - float(step["start_x"]) - STAIR_PLATFORM_LENGTH) < 1e-4
            for step in steps
        ))
        self.assertTrue(all(
            abs(float(gap["end_x"]) - float(gap["start_x"]) - STAIR_GAP_LENGTH) < 1e-4
            for gap in gaps
        ))
        heights = [float(step["surface_y"]) for step in steps]
        self.assertEqual(
            [round(b - a, 2) for a, b in zip(heights, heights[1:])],
            [STAIR_STEP_RISE, STAIR_STEP_RISE, STAIR_STEP_RISE],
        )
        self.assertTrue(all(gap["failure_destination"] == "SAFE" for gap in gaps))

    def test_staircase_adds_optional_mastery_but_no_required_actions(self) -> None:
        overlay = self.plan["prototype_overlays"]["fork_topology_vocabulary_v1"]
        self.assertFalse(overlay["new_required_actions"])
        selected = overlay["selected"]
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["target_time"], 102.5)
        self.assertEqual(selected[0]["optional_mastery_actions"], 3)
        self.assertFalse(selected[0]["virtuoso_available"])

    def test_renderer_uses_each_technical_segments_surface_y(self) -> None:
        self.assertIn('segment.get("surface_y", technical["elevation"])', COMPILER)
        self.assertIn('name="GracefulOpening0120ClimaxFork"', self.scene)
        self.assertGreaterEqual(self.scene.count('name="TechnicalRoute'), 1)

    def test_flow_tracker_can_fail_down_from_technical_to_safe(self) -> None:
        self.assertIn('event["route"] = &"SAFE"', FLOW)
        self.assertIn('world_y <= route_threshold', FLOW)
        self.assertIn('world_x < float(event["merge_x"])', FLOW)

    def test_extension_is_deterministic(self) -> None:
        base, spatial, plan = build_120_second_extension(
            DEMANDS,
            VISUAL,
            ACCEPTED_90,
        )
        self.assertEqual(self.base, base)
        self.assertEqual(self.spatial, spatial)
        self.assertEqual(self.plan, plan)
        self.assertEqual(self.scene, render_climax_fork_scene(plan))


if __name__ == "__main__":
    unittest.main()
