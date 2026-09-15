from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

from analyze import SCHEMA_VERSION, analyze_audio


ROOT = Path(__file__).resolve().parents[2]
AUDIO = ROOT / "assets/audio/graceful_opening.mp3"


class MusicAnalyzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.first = analyze_audio(AUDIO)
        cls.second = analyze_audio(AUDIO)

    def test_schema_and_deterministic_output(self) -> None:
        self.assertEqual(self.first["schema_version"], SCHEMA_VERSION)
        self.assertEqual(self.first, self.second)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "analysis.json"
            output.write_text(json.dumps(self.first, allow_nan=False), encoding="utf-8")
            self.assertEqual(json.loads(output.read_text(encoding="utf-8")), self.first)

    def test_events_are_valid_and_sorted(self) -> None:
        duration = self.first["source"]["duration_seconds"]
        collections = [
            self.first["tempo"]["beats"],
            [item["time"] for item in self.first["accents"]],
            [item["time"] for item in self.first["energy"]],
            [item["time"] for item in self.first["rhythmic_density"]],
            [item["time"] for item in self.first["sustain"]["points"]],
            [item["time"] for item in self.first["boundaries"]],
            [item["time"] for item in self.first["climax_candidates"]],
        ]
        for timestamps in collections:
            self.assertEqual(timestamps, sorted(timestamps))
            self.assertTrue(all(0.0 <= value <= duration for value in timestamps))

    def test_normalized_values_and_finite_numbers(self) -> None:
        normalized = (
            self.first["accents"]
            + self.first["energy"]
            + self.first["rhythmic_density"]
            + self.first["sustain"]["points"]
            + self.first["boundaries"]
            + self.first["climax_candidates"]
        )
        for item in normalized:
            key = "strength" if "strength" in item else "value"
            self.assertTrue(0.0 <= item[key] <= 1.0)
            self.assertTrue(all(math.isfinite(value) for value in item.values() if isinstance(value, float)))

    def test_beats_and_first_30_seconds_are_analyzable(self) -> None:
        self.assertTrue(self.first["tempo"]["beats"])
        self.assertTrue(any(item["time"] <= 30.0 for item in self.first["accents"]))
        self.assertTrue(any(item["time"] <= 30.0 for item in self.first["boundaries"]))
        self.assertTrue(any(item["time"] <= 30.0 for item in self.first["climax_candidates"]))


if __name__ == "__main__":
    unittest.main()
