from __future__ import annotations

import json
import math
import unittest
from pathlib import Path

from extract_segment_features import extract_segment


ROOT = Path(__file__).resolve().parents[2]
DATASET_PATH = ROOT / "data/choreography/classical_reference_v0_1.json"
SCHEMA_PATH = ROOT / "data/choreography/classical_reference_schema_v0_1.json"
AUDIO_PATH = ROOT / "assets/audio/graceful_opening.mp3"


class ClassicalReferenceDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.dataset = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.examples = cls.dataset["examples"]

    def test_versioned_contract_and_unique_ids(self) -> None:
        self.assertEqual(self.dataset["schema_version"], "0.1")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "0.1")
        identifiers = [example["id"] for example in self.examples]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        self.assertTrue(all(identifier and identifier == identifier.lower() for identifier in identifiers))

    def test_controlled_vocabulary_and_normalized_annotations(self) -> None:
        vocabulary = self.dataset["controlled_vocabulary"]
        for example in self.examples:
            self.assertIn(example["dataset_split"], {"gold", "holdout"})
            self.assertIn(example["movement_class"], vocabulary["movement_class"])
            self.assertTrue(set(example["movement_function"]).issubset(vocabulary["movement_function"]))
            self.assertTrue(set(example["movement_quality"]).issubset(vocabulary["movement_quality"]))
            self.assertTrue(0.0 <= example["annotation_confidence"] <= 1.0)
            self.assertTrue(all(0.0 <= value <= 1.0 for value in example["movement_demand"].values()))

    def test_gold_provenance_and_no_fabricated_audio_features(self) -> None:
        gold = [example for example in self.examples if example["dataset_split"] == "gold"]
        self.assertGreaterEqual(len(gold), 10)
        for example in gold:
            provenance = example["provenance"]
            self.assertTrue(provenance["source_title"])
            self.assertTrue(provenance["source_url"].startswith("https://"))
            self.assertIn(provenance["confidence"], {"high", "medium"})
        for example in self.examples:
            alignment = example["music_alignment"]
            self.assertEqual(alignment["feature_status"], "not_extracted")
            self.assertIsNone(alignment["audio_reference"])
            self.assertIsNone(alignment["audio_features"])

    def test_holdout_is_explicit_and_excluded_from_gold(self) -> None:
        holdout = [example for example in self.examples if example["dataset_split"] == "holdout"]
        gold_ids = {example["id"] for example in self.examples if example["dataset_split"] == "gold"}
        self.assertGreaterEqual(len(holdout), 1)
        self.assertTrue(all(example["work"] == "Paquita" for example in holdout))
        self.assertTrue(all(example["id"] not in gold_ids for example in holdout))

    def test_gold_jump_scale_coverage_and_ordering(self) -> None:
        gold = [example for example in self.examples if example["dataset_split"] == "gold"]
        jump_classes = ("SMALL_JUMP", "MEDIUM_JUMP", "LARGE_TRAVELLING_LEAP")
        grouped = {
            movement_class: [
                example for example in gold if example["movement_class"] == movement_class
            ]
            for movement_class in jump_classes
        }
        self.assertTrue(all(grouped.values()))
        self.assertGreaterEqual(len(grouped["MEDIUM_JUMP"]), 2)

        def mean_demand(movement_class: str, demand: str) -> float:
            values = [example["movement_demand"][demand] for example in grouped[movement_class]]
            return sum(values) / len(values)

        small_scale = mean_demand("SMALL_JUMP", "movement_scale")
        medium_scale = mean_demand("MEDIUM_JUMP", "movement_scale")
        large_scale = mean_demand("LARGE_TRAVELLING_LEAP", "movement_scale")
        self.assertGreater(large_scale, medium_scale)
        self.assertGreater(medium_scale, small_scale)
        self.assertGreater(
            mean_demand("LARGE_TRAVELLING_LEAP", "travel"),
            mean_demand("SMALL_JUMP", "travel"),
        )

    def test_all_numeric_values_are_finite(self) -> None:
        def walk(value: object) -> None:
            if isinstance(value, float):
                self.assertTrue(math.isfinite(value))
            elif isinstance(value, dict):
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)
        walk(self.dataset)

    def test_segment_extraction_is_deterministic(self) -> None:
        first = extract_segment(AUDIO_PATH, 0.0, 8.0)
        second = extract_segment(AUDIO_PATH, 0.0, 8.0)
        self.assertEqual(first, second)
        self.assertTrue(first["tempo"]["beat_count"] > 0)
        self.assertTrue(all(math.isfinite(value) for value in (
            first["tempo"]["estimated_bpm"], first["onset"]["strongest"],
            first["energy"]["mean"], first["energy"]["mean_delta"],
            first["rhythmic_density"]["mean"], first["sustain"]["mean"],
        )))


if __name__ == "__main__":
    unittest.main()
