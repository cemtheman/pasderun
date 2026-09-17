from __future__ import annotations

import json
import math
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
PARALLAX = ROOT / "scenes/gameplay/parallax_presentation.gd"
ANALYSIS = ROOT / "data/music/graceful_opening.analysis.json"


class FullAudioRunwayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.generated = GENERATED.read_text(encoding="utf-8")
        cls.dancer = DANCER.read_text(encoding="utf-8")
        cls.parallax = PARALLAX.read_text(encoding="utf-8")
        cls.analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))

    def test_active_audio_duration_and_run_speed_drive_required_length(self) -> None:
        self.assertIn(
            'path="res://assets/audio/graceful_opening.mp3"',
            self.runtime,
        )
        duration = float(self.analysis["source"]["duration_seconds"])
        run_speed = float(
            re.search(r"run_speed: float = ([0-9.]+)", self.dancer).group(1)
        )
        self.assertTrue(math.isclose(duration, 140.016, abs_tol=0.001))
        self.assertEqual(run_speed, 4.0)
        self.assertTrue(math.isclose(run_speed * (duration + 5.0), 580.064))

    def test_one_neutral_continuation_covers_audio_plus_five_seconds(self) -> None:
        continuation = re.search(
            r'\[node name="FullAudioContinuation".*?(?=\n\[node name="ForkDebugVisualization")',
            self.runtime,
            re.DOTALL,
        ).group(0)
        center_x = float(
            re.search(r"position = Vector3\(([0-9.]+),", continuation).group(1)
        )
        length = float(
            re.search(
                r'\[sub_resource type="BoxMesh" id="BoxMesh_full_audio_continuation"\]\n'
                r"size = Vector3\(([0-9.]+),",
                self.runtime,
            ).group(1)
        )
        authored_end = 109.05 + 37.9 / 2.0
        continuation_start = center_x - length / 2.0
        continuation_end = center_x + length / 2.0
        required_end = 4.0 * (140.016 + 5.0)
        self.assertTrue(math.isclose(authored_end, continuation_start))
        self.assertGreaterEqual(continuation_end, required_end)
        self.assertEqual(self.runtime.count('name="FullAudioContinuation"'), 1)
        self.assertNotIn('type="Marker3D" parent="FullAudioContinuation"', self.runtime)
        self.assertNotIn('type="Area3D" parent="FullAudioContinuation"', self.runtime)

    def test_continuation_mesh_and_collision_are_identical(self) -> None:
        expected_size = "size = Vector3(452.064, 0.5, 4)"
        self.assertEqual(self.runtime.count(expected_size), 2)
        self.assertIn('mesh = SubResource("BoxMesh_full_audio_continuation")', self.runtime)
        self.assertIn(
            'shape = SubResource("BoxShape_full_audio_continuation")',
            self.runtime,
        )

    def test_authored_geometry_and_events_remain_separate_and_unchanged(self) -> None:
        self.assertEqual(self.generated.count('type="Marker3D" parent="Events"'), 6)
        self.assertNotIn("FullAudioContinuation", self.generated)

    def test_parallax_uses_one_global_fifteen_percent_multiplier(self) -> None:
        self.assertIn("pace_multiplier: float = 1.15", self.parallax)
        self.assertIn("paced_progress_x := progress_x * pace_multiplier", self.parallax)
        self.assertEqual(self.parallax.count("paced_progress_x *"), 3)
        factors = [
            float(value)
            for value in re.findall(
                r"(?:far|mid|foreground)_factor: float = ([0-9.]+)",
                self.parallax,
            )
        ]
        self.assertEqual(factors, [0.005, 0.010, 0.018])
        self.assertLess(factors[0], factors[1])
        self.assertLess(factors[1], factors[2])
        self.assertNotIn("position.y", self.parallax)
        self.assertNotIn(".new()", self.parallax)


if __name__ == "__main__":
    unittest.main()
