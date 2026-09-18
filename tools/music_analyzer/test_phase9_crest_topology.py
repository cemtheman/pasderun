from __future__ import annotations

import json
import unittest
from pathlib import Path

from build_crest_refinement import (
    CREST_HEIGHTS,
    ENTRY_LANDING_LENGTH,
    build_crest_refinement,
    select_crest_anchor,
)
from build_climax_fork import render_climax_fork_scene
from fork_topology_vocabulary import CREST, classify_topology


ROOT = Path(__file__).resolve().parents[2]
VISUAL = json.loads(
    (ROOT / "data/music/graceful_opening.visual_score_v0_1.json").read_text(encoding="utf-8")
)
BASELINE = json.loads(
    (ROOT / "data/geometry/graceful_opening_00_120_topology_v1.geometry_plan_v0_1.json").read_text(encoding="utf-8")
)


class Phase9CrestTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.plan = build_crest_refinement(BASELINE, VISUAL)
        cls.scene = render_climax_fork_scene(cls.plan)
        cls.event = next(
            event for event in cls.plan["events"]
            if float(event["source_time"]) == 68.5
        )
        cls.baseline_event = next(
            event for event in BASELINE["events"]
            if float(event["source_time"]) == 68.5
        )

    def test_music_rule_selects_68_5_as_crest(self) -> None:
        anchor = select_crest_anchor(VISUAL, BASELINE)
        self.assertEqual(float(anchor["time"]), 68.5)
        self.assertEqual(classify_topology(VISUAL, anchor), CREST)

    def test_crest_keeps_existing_fork_timing_safe_route_and_merge(self) -> None:
        self.assertEqual(self.event["geometry"], self.baseline_event["geometry"])
        self.assertEqual(
            self.event["branch"]["routes"]["safe"],
            self.baseline_event["branch"]["routes"]["safe"],
        )
        self.assertEqual(
            self.event["branch"]["merge"],
            self.baseline_event["branch"]["merge"],
        )

    def test_crest_replaces_only_flat_upper_runway_with_rise_and_fall(self) -> None:
        technical = self.event["branch"]["routes"]["technical"]
        terraces = [
            segment for segment in technical["segments"]
            if str(segment["type"]).startswith("CREST_TERRACE_")
        ]
        self.assertEqual(len(terraces), len(CREST_HEIGHTS))
        self.assertEqual(
            [float(segment["surface_y"]) for segment in terraces],
            list(CREST_HEIGHTS),
        )
        self.assertAlmostEqual(
            float(terraces[0]["end_x"]) - float(terraces[0]["start_x"]),
            ENTRY_LANDING_LENGTH,
            places=4,
        )
        self.assertEqual(technical["profile"], "STEPPED_CREST")
        self.assertEqual(technical["peak_elevation"], max(CREST_HEIGHTS))

    def test_crest_adds_no_new_required_input(self) -> None:
        overlay = self.plan["prototype_overlays"]["fork_topology_v1_1"]
        self.assertFalse(overlay["new_required_actions"])
        self.assertFalse(overlay["safe_route_changed"])
        self.assertFalse(overlay["fork_timing_changed"])
        self.assertFalse(overlay["merge_changed"])

    def test_crescendo_staircase_remains_byte_equivalent_in_plan_data(self) -> None:
        expected = next(
            event for event in BASELINE["events"]
            if float(event["source_time"]) == 102.5
        )
        actual = next(
            event for event in self.plan["events"]
            if float(event["source_time"]) == 102.5
        )
        self.assertEqual(actual, expected)

    def test_zero_to_sixty_event_contract_remains_unchanged(self) -> None:
        expected = [
            event for event in BASELINE["events"]
            if float(event["source_time"]) <= 60.0
        ]
        actual = [
            event for event in self.plan["events"]
            if float(event["source_time"]) <= 60.0
        ]
        self.assertEqual(actual, expected)

    def test_scene_contains_crest_terraces_at_distinct_heights(self) -> None:
        self.assertIn('name="GracefulOpening0120ClimaxFork"', self.scene)
        # Five collision terraces replace the former single upper runway.
        for index in range(1, 6):
            self.assertIn(f'TechnicalRoute', self.scene)
        self.assertIn('position = Vector3(275.3000, -0.2500, 0)', self.scene)
        self.assertIn('position = Vector3(276.', self.scene)

    def test_refinement_is_deterministic(self) -> None:
        again = build_crest_refinement(BASELINE, VISUAL)
        self.assertEqual(self.plan, again)
        self.assertEqual(self.scene, render_climax_fork_scene(again))


if __name__ == "__main__":
    unittest.main()
