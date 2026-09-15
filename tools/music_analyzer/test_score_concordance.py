from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONCORDANCE_PATH = ROOT / "data/music_profiles/classical_score_concordance_v0_1.json"
SCHEMA_PATH = ROOT / "data/music_profiles/classical_score_concordance_schema_v0_1.json"
CHOREOGRAPHY_PATH = ROOT / "data/choreography/classical_reference_v0_1.json"


class ScoreConcordanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(CONCORDANCE_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.choreography = json.loads(CHOREOGRAPHY_PATH.read_text(encoding="utf-8"))
        cls.records = cls.data["records"]

    def test_version_and_unique_known_choreography_ids(self) -> None:
        self.assertEqual(self.data["schema_version"], "0.1")
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], "0.1")
        identifiers = [record["choreography_example_id"] for record in self.records]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        known = {example["id"] for example in self.choreography["examples"]}
        self.assertTrue(set(identifiers).issubset(known))

    def test_exact_score_source_metadata_and_urls(self) -> None:
        required = {
            "edition_title", "editor", "publisher", "publication_year", "source_url",
            "rights_status", "source_identifier", "checksum_sha256",
        }
        for record in self.records:
            source = record["score_source"]
            self.assertEqual(set(source), required)
            for key in required - {"editor", "checksum_sha256"}:
                self.assertTrue(source[key])
            self.assertTrue(source["source_url"].startswith("https://"))
            checksum = source["checksum_sha256"]
            self.assertTrue(checksum is None or re.fullmatch(r"[0-9a-f]{64}", checksum))

    def test_status_confidence_and_location_policy(self) -> None:
        allowed = set(self.data["status_vocabulary"])
        for record in self.records:
            self.assertIn(record["status"], allowed)
            confidence = record["mapping_evidence"]["mapping_confidence"]
            self.assertTrue(0.0 <= confidence <= 1.0)
            self.assertTrue(record["mapping_evidence"]["basis"])
            self.assertTrue(record["mapping_evidence"]["notes"])
            location = record["score_location"]
            if record["status"] == "confirmed":
                self.assertTrue(location["act"])
                self.assertTrue(location["number"])
                self.assertTrue(
                    location["measure_start"] is not None
                    or location["pdf_page_start"] is not None
                    or location["printed_page_start"] is not None
                )

    def test_unresolved_is_allowed_and_probable_has_number_level_location(self) -> None:
        self.assertTrue(any(record["status"] == "unresolved" for record in self.records))
        for record in self.records:
            if record["status"] == "probable":
                self.assertTrue(record["score_location"]["act"])
                self.assertTrue(record["score_location"]["number"])

    def test_no_musical_features_exist(self) -> None:
        forbidden_keys = {
            "audio_features", "tempo", "pulse", "rhythmic_density", "accent_character",
            "energy_shape", "sustain_character", "phrase_position", "climax_role",
        }

        def walk(value: object) -> None:
            if isinstance(value, dict):
                self.assertTrue(forbidden_keys.isdisjoint(value.keys()))
                for child in value.values():
                    walk(child)
            elif isinstance(value, list):
                for child in value:
                    walk(child)

        walk(self.data)


if __name__ == "__main__":
    unittest.main()
