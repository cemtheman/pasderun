from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from build_visual_score import (
    BEATS_PER_WINDOW,
    GRAVITY,
    JUMP_VELOCITY,
    LOW_TRANSITION_DURATION,
    MAX_PASSIVE_STEP_HEIGHT,
    MAX_TRAVERSABLE_STEP_HEIGHT,
    MIN_REQUIRED_ACTION_SPACING_SECONDS,
    RUN_SPEED,
    build_visual_score,
)


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS = ROOT / "data/music/graceful_opening.analysis.json"
DEMANDS = ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json"
SCHEMA = ROOT / "data/music/graceful_opening_visual_score_schema_v0_1.json"


class Phase9VisualScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
        cls.demands = json.loads(DEMANDS.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.score = build_visual_score(cls.analysis, cls.demands)

    def test_visual_score_is_continuous_enough_to_show_music_between_events(self) -> None:
        windows = [
            window for window in self.score["windows"]
            if window["start"] < 60.0 and window["end"] > 30.0
        ]
        self.assertGreaterEqual(len(windows), 15)
        self.assertTrue(all(window["beat_span"]["count"] <= BEATS_PER_WINDOW for window in windows))
        self.assertTrue(all(window["duration"] < 2.2 for window in windows))

        roles = {window["visual_intent"]["phrase_role"] for window in windows}
        self.assertIn("CLIMAX", roles)
        self.assertGreaterEqual(len(roles), 3)

    def test_visual_score_separates_passive_expression_from_required_input(self) -> None:
        for window in self.score["windows"]:
            self.assertTrue(window["interaction_budget"]["passive_spatial_change"])
            self.assertEqual(window["interaction_budget"]["max_required_actions"], 2)

        anchors = [
            anchor for anchor in self.score["event_anchors"]
            if 30.0 < anchor["time"] <= 60.0
        ]
        self.assertGreaterEqual(len(anchors), 9)
        self.assertTrue(any(anchor["interaction"]["required"] for anchor in anchors))

    def test_playability_gate_is_derived_from_controller_limits_with_margin(self) -> None:
        gate = self.score["playability_gate"]
        controller = gate["controller"]
        limits = gate["design_limits"]

        expected_airtime = 2.0 * JUMP_VELOCITY / GRAVITY
        self.assertAlmostEqual(controller["jump_airtime_seconds"], expected_airtime, places=4)
        self.assertAlmostEqual(
            controller["same_height_jump_range_world"],
            expected_airtime * RUN_SPEED,
            places=4,
        )
        self.assertAlmostEqual(
            controller["low_transition_distance_world"],
            LOW_TRANSITION_DURATION * RUN_SPEED,
            places=4,
        )
        self.assertLess(MAX_PASSIVE_STEP_HEIGHT, MAX_TRAVERSABLE_STEP_HEIGHT)
        self.assertLess(limits["max_gap_world"], controller["same_height_jump_range_world"])
        self.assertLess(
            limits["low_passage_max_length_world"],
            controller["low_transition_distance_world"],
        )
        self.assertEqual(limits["required_input_concurrency"], 1)

    def test_required_actions_never_exceed_player_load_spacing(self) -> None:
        required = [
            anchor for anchor in self.score["event_anchors"]
            if anchor["interaction"]["required"]
        ]
        times = [anchor["time"] for anchor in required]
        for earlier, later in zip(times, times[1:]):
            self.assertGreaterEqual(
                later - earlier,
                MIN_REQUIRED_ACTION_SPACING_SECONDS - 1e-6,
            )

        for earlier, later in zip(required, required[1:]):
            occupied_until = (
                earlier["time"]
                + earlier["interaction"]["occupancy_seconds"]
            )
            self.assertGreaterEqual(later["time"] + 1e-6, occupied_until)

    def test_required_actions_respect_four_beat_window_budget(self) -> None:
        counts: dict[int, int] = {}
        for anchor in self.score["event_anchors"]:
            if not anchor["interaction"]["required"]:
                continue
            window_index = int(anchor["window_index"])
            counts[window_index] = counts.get(window_index, 0) + 1
        self.assertTrue(all(count <= 2 for count in counts.values()))

    def test_score_preserves_all_movement_events_even_when_interaction_is_suppressed(self) -> None:
        self.assertEqual(
            [anchor["time"] for anchor in self.score["event_anchors"]],
            [round(float(event["time"]), 3) for event in self.demands["events"]],
        )
        for anchor in self.score["event_anchors"]:
            if not anchor["interaction"]["required"]:
                action = anchor["interaction"]["candidate_action"]
                reason = anchor["interaction"]["suppression_reason"]
                self.assertTrue(
                    action is None
                    or reason in {"required_action_spacing", "required_action_overlap", "window_action_budget"}
                )

    def test_visual_score_contains_no_geometry_coordinates(self) -> None:
        forbidden = {"x", "world_x", "position", "geometry", "obstacle"}

        def walk(value: object) -> None:
            if isinstance(value, dict):
                self.assertTrue(forbidden.isdisjoint(value.keys()))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
            elif isinstance(value, float):
                self.assertTrue(math.isfinite(value))

        walk(self.score)

    def test_schema_declares_visual_score_contract(self) -> None:
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "0.1")
        self.assertIn("windows", self.schema["required"])
        self.assertIn("playability_gate", self.schema["required"])
        self.assertIn("event_anchors", self.schema["required"])


if __name__ == "__main__":
    unittest.main()
