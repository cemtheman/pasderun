from __future__ import annotations

import json
import unittest
from pathlib import Path

from build_spatial_score import (
    DEFAULT_END_SECONDS,
    DEFAULT_START_SECONDS,
    MAX_PASSIVE_DELTA_Y,
    build_spatial_score,
)


ROOT = Path(__file__).resolve().parents[2]
VISUAL_SCORE = ROOT / "data/music/graceful_opening.visual_score_v0_1.json"
GEOMETRY_PLAN = ROOT / "data/geometry/graceful_opening_00_60.geometry_plan_v0_1.json"
SCHEMA = ROOT / "data/geometry/graceful_opening_spatial_score_schema_v0_1.json"


class Phase9SpatialScoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.visual = json.loads(VISUAL_SCORE.read_text(encoding="utf-8"))
        cls.geometry = json.loads(GEOMETRY_PLAN.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.spatial = build_spatial_score(cls.visual, cls.geometry)

    def test_spatial_score_only_reshapes_existing_runway_coverage(self) -> None:
        self.assertTrue(self.spatial["policy"]["event_geometry_preserved"])
        self.assertFalse(self.spatial["policy"]["new_required_actions"])
        self.assertFalse(self.spatial["policy"]["new_gaps"])

        run_speed = self.visual["playability_gate"]["controller"]["run_speed"]
        start_x = DEFAULT_START_SECONDS * run_speed
        end_x = DEFAULT_END_SECONDS * run_speed
        expected = 0.0
        for runway in self.geometry["surface_plan"]["runway_intervals"]:
            left = max(start_x, float(runway["start_x"]))
            right = min(end_x, float(runway["end_x"]))
            expected += max(0.0, right - left)

        actual = sum(float(segment["length"]) for segment in self.spatial["segments"])
        self.assertAlmostEqual(actual, expected, places=3)

    def test_existing_gap_holes_remain_holes(self) -> None:
        gap_intervals = [
            (float(event["geometry"]["start_x"]), float(event["geometry"]["end_x"]))
            for event in self.geometry["events"]
            if DEFAULT_START_SECONDS <= float(event["source_time"]) <= DEFAULT_END_SECONDS
            and event["geometry"]["type"].endswith("_GAP")
        ]
        self.assertEqual(len(gap_intervals), 4)

        for segment in self.spatial["segments"]:
            for gap_start, gap_end in gap_intervals:
                overlap = min(float(segment["end_x"]), gap_end) - max(float(segment["start_x"]), gap_start)
                self.assertLessEqual(overlap, 1e-6)

    def test_passive_surface_steps_remain_below_controller_limit(self) -> None:
        controller_limit = float(
            self.visual["playability_gate"]["controller"]["max_traversable_step_height"]
        )
        design_limit = float(
            self.visual["playability_gate"]["design_limits"]["max_passive_step_height"]
        )
        self.assertAlmostEqual(MAX_PASSIVE_DELTA_Y * 2.0, design_limit, places=6)
        self.assertLess(design_limit, controller_limit)

        segments = self.spatial["segments"]
        for segment in segments:
            self.assertLessEqual(abs(float(segment["delta_y"])), MAX_PASSIVE_DELTA_Y + 1e-6)

        for earlier, later in zip(segments, segments[1:]):
            if abs(float(earlier["end_x"]) - float(later["start_x"])) > 1e-5:
                continue
            step = abs(float(later["surface_y"]) - float(earlier["surface_y"]))
            self.assertLessEqual(step, design_limit + 1e-6)

    def test_only_geometry_sensitive_actions_are_flat_locked(self) -> None:
        self.assertEqual(len(self.spatial["action_locks"]), 4)
        self.assertEqual(
            {lock["action"] for lock in self.spatial["action_locks"]},
            {"JUMP"},
        )
        self.assertTrue(
            all(float(lock["time"]) < DEFAULT_END_SECONDS for lock in self.spatial["action_locks"])
        )
        self.assertNotIn(
            60.604,
            [float(lock["time"]) for lock in self.spatial["action_locks"]],
        )
        locked_segments = [
            segment for segment in self.spatial["segments"]
            if segment["interaction_lock"] is not None
        ]
        self.assertTrue(locked_segments)
        self.assertTrue(all(float(segment["delta_y"]) == 0.0 for segment in locked_segments))

        for lock in self.spatial["action_locks"]:
            covered = [
                segment for segment in locked_segments
                if max(float(segment["start_x"]), float(lock["start_x"]))
                < min(float(segment["end_x"]), float(lock["end_x"]))
            ]
            self.assertTrue(covered, lock)

    def test_30_to_60_has_varied_passive_spatial_vocabulary(self) -> None:
        patterns = {
            segment["pattern"]
            for segment in self.spatial["segments"]
            if segment["pattern"] != "ACTION_LOCK"
        }
        self.assertGreaterEqual(len(patterns), 5)
        self.assertIn("LIFTED_TERRACE", patterns)
        self.assertIn("FALLING_TERRACE", patterns)
        self.assertIn("PULSE_STEPS", patterns)
        self.assertIn("RISING_TERRACE", patterns)

    def test_unlocked_runway_is_subdivided_to_beat_scale(self) -> None:
        run_speed = float(self.visual["playability_gate"]["controller"]["run_speed"])
        for segment in self.spatial["segments"]:
            if segment["interaction_lock"] is not None:
                continue
            window = self.visual["windows"][int(segment["source_window_index"])]
            beat_count = max(1, int(window["beat_span"]["count"]))
            beat_length = float(window["duration"]) * run_speed / beat_count
            self.assertLessEqual(float(segment["length"]), beat_length + 1e-4)

    def test_pulse_and_build_patterns_have_internal_shape(self) -> None:
        pulse_groups: dict[int, list[dict[str, object]]] = {}
        build_segments: list[dict[str, object]] = []
        for segment in self.spatial["segments"]:
            if segment["interaction_lock"] is not None:
                continue
            if segment["pattern"] == "PULSE_STEPS":
                pulse_groups.setdefault(int(segment["source_window_index"]), []).append(segment)
            if segment["pattern"] == "RISING_TERRACE":
                build_segments.append(segment)

        self.assertTrue(
            any(
                len({float(segment["delta_y"]) for segment in group}) >= 2
                for group in pulse_groups.values()
            )
        )

        self.assertGreaterEqual(len(build_segments), 3)
        build_segments.sort(key=lambda segment: float(segment["start_x"]))
        build_deltas = [float(segment["delta_y"]) for segment in build_segments]
        self.assertEqual(build_deltas, sorted(build_deltas))

    def test_schema_declares_spatial_score_contract(self) -> None:
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "0.1")
        self.assertIn("segments", self.schema["required"])
        self.assertIn("action_locks", self.schema["required"])
        self.assertIn("policy", self.schema["required"])


if __name__ == "__main__":
    unittest.main()
