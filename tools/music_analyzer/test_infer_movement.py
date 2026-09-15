from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from infer_movement import MOVEMENT_CLASSES, infer_movements


ROOT = Path(__file__).resolve().parents[2]
ANALYSIS_PATH = ROOT / "data/music/graceful_opening.analysis.json"
OUTPUT_PATH = ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json"
SCHEMA_PATH = ROOT / "data/choreography/graceful_opening_movement_demands_schema_v0_1.json"


class MovementInferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.analysis = json.loads(ANALYSIS_PATH.read_text(encoding="utf-8"))
        cls.output = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_versioned_contract_and_ordered_bounded_time(self) -> None:
        self.assertEqual(self.output["schema_version"], "0.1")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "0.1")
        times = [event["time"] for event in self.output["events"]]
        self.assertEqual(times, sorted(times))
        self.assertTrue(all(0 <= time <= self.output["duration_seconds"] for time in times))
        self.assertTrue(all(event["window_start"] <= event["time"] <= event["window_end"] for event in self.output["events"]))

    def test_normalized_demands_confidence_and_branchability(self) -> None:
        for event in self.output["events"]:
            self.assertTrue(all(0.0 <= value <= 1.0 for value in event["movement_demand"].values()))
            self.assertTrue(0.0 <= event["branchability"] <= 1.0)
            self.assertTrue(all(0.0 <= item["confidence"] <= 1.0 for item in event["candidate_classes"]))

    def test_controlled_vocabulary_explanations_and_no_grand_jete(self) -> None:
        allowed = set(MOVEMENT_CLASSES)
        observed = set()
        for event in self.output["events"]:
            self.assertTrue(event["explanation"])
            classes = {item["class"] for item in event["candidate_classes"]}
            self.assertTrue(classes.issubset(allowed))
            observed.update(classes)
        self.assertNotIn("GRAND_JETE", observed)
        self.assertTrue({"SMALL_JUMP", "MEDIUM_JUMP", "LARGE_TRAVELLING_LEAP"}.issubset(observed))
        self.assertTrue({"TRAVEL", "ACCENT_ACTION", "SUSTAINED_BALANCE", "RECOVERY"}.issubset(observed))

    def test_deterministic_output(self) -> None:
        first = infer_movements(self.analysis)
        second = infer_movements(self.analysis)
        self.assertEqual(first, second)
        self.assertEqual(first, self.output)

    def test_no_geometry_coordinates_or_non_finite_numbers(self) -> None:
        forbidden = {"x", "world_x", "position", "geometry", "obstacle", "route_fork"}

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

        walk(self.output)

    def test_first_30_seconds_has_meaningful_candidates(self) -> None:
        early = [event for event in self.output["events"] if event["time"] <= 30.0]
        self.assertGreaterEqual(len(early), 5)
        self.assertTrue(any(event["musical_context"]["climax_strength"] >= 0.8 for event in early))
        self.assertTrue(any(event["candidate_classes"][0]["confidence"] >= 0.7 for event in early))


if __name__ == "__main__":
    unittest.main()
