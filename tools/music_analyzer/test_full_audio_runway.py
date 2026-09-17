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

    def _extended_surfaces(self) -> list[tuple[str, float, float, float]]:
        mesh_lengths = {
            resource: float(length)
            for resource, length in re.findall(
                r'\[sub_resource type="BoxMesh" id="(BoxMesh_(?:neutral|technical)_[0-9_]+)"\]\n'
                r"size = Vector3\(([0-9.]+), 0.5, 4\)",
                self.runtime,
            )
        }
        surfaces = []
        for name, center, elevation in re.findall(
            r'\[node name="([^"]+)" type="StaticBody3D" parent="ExtendedCourse"\]\n'
            r"position = Vector3\(([0-9.]+), (-?[0-9.]+), 0\)",
            self.runtime,
        ):
            resource = re.search(
                rf'parent="ExtendedCourse/{re.escape(name)}"\]\n'
                rf'mesh = SubResource\("([^"]+)"\)',
                self.runtime,
            ).group(1)
            surfaces.append((name, float(center), float(elevation), mesh_lengths[resource]))
        return sorted(surfaces, key=lambda surface: surface[1])

    def test_extended_course_covers_audio_plus_five_seconds(self) -> None:
        surfaces = self._extended_surfaces()
        authored_end = 109.05 + 37.9 / 2.0
        course_start = surfaces[0][1] - surfaces[0][3] / 2.0
        course_end = surfaces[-1][1] + surfaces[-1][3] / 2.0
        required_end = 4.0 * (140.016 + 5.0)
        self.assertTrue(math.isclose(authored_end, course_start))
        self.assertGreaterEqual(course_end, required_end)
        self.assertNotIn('type="Marker3D" parent="ExtendedCourse"', self.runtime)
        self.assertNotIn('type="Area3D" parent="ExtendedCourse"', self.runtime)

    def test_fourteen_platforms_form_eight_controller_safe_gaps(self) -> None:
        surfaces = self._extended_surfaces()
        technical = [surface for surface in surfaces if surface[0].startswith("TechnicalPlatform")]
        self.assertEqual(len(technical), 14)
        self.assertEqual(
            [surface[3] for surface in technical],
            [13.0, 12.0, 11.0, 10.0, 8.0, 7.5, 8.0, 8.0, 7.0, 8.0, 8.0, 8.0, 7.5, 12.0],
        )

        gaps = []
        for left, right in zip(surfaces, surfaces[1:]):
            left_end = left[1] + left[3] / 2.0
            right_start = right[1] - right[3] / 2.0
            if right_start - left_end > 0.001:
                gaps.append(right_start - left_end)
        proven_jump_range = 4.0 * (2.0 * 6.0 / 18.0)
        self.assertEqual(len(gaps), 8)
        self.assertTrue(all(1.499 <= gap <= 1.701 for gap in gaps))
        self.assertTrue(all(gap < proven_jump_range * 0.65 for gap in gaps))

    def test_every_extended_surface_has_matching_mesh_and_collision(self) -> None:
        surfaces = self._extended_surfaces()
        self.assertEqual(len(surfaces), 20)
        for name, _, _, _ in surfaces:
            block = re.search(
                rf'\[node name="{re.escape(name)}".*?(?=\n\[node name="(?:NeutralRunway|TechnicalPlatform|ForkDebugVisualization))',
                self.runtime,
                re.DOTALL,
            ).group(0)
            mesh_resource = re.search(r'mesh = SubResource\("BoxMesh_([^"]+)"\)', block).group(1)
            shape_resource = re.search(r'shape = SubResource\("BoxShape_([^"]+)"\)', block).group(1)
            self.assertEqual(mesh_resource, shape_resource)

    def test_authored_geometry_and_events_remain_separate_and_unchanged(self) -> None:
        self.assertEqual(self.generated.count('type="Marker3D" parent="Events"'), 6)
        self.assertNotIn("FullAudioContinuation", self.generated)

    def test_late_groups_use_safe_progressive_elevation(self) -> None:
        surfaces = self._extended_surfaces()
        technical = [surface for surface in surfaces if surface[0].startswith("TechnicalPlatform")]
        late = technical[4:]
        self.assertEqual([surface[2] for surface in late], [-2.8, -2.55, -2.8, -2.8, -2.55, -2.8, -2.55, -2.8, -2.3, -2.55])
        self.assertTrue(all(abs(right[2] - left[2]) <= 0.5 for left, right in zip(late, late[1:])))
        self.assertEqual(technical[-1][1] + technical[-1][3] / 2.0, 539.2)
        self.assertGreater(surfaces[-1][3], 40.0)

    def test_technical_groups_are_distributed_across_extension(self) -> None:
        technical = [surface for surface in self._extended_surfaces() if surface[0].startswith("TechnicalPlatform")]
        group_centers = [
            sum(surface[1] for surface in technical[start:end]) / (end - start)
            for start, end in ((0, 2), (2, 4), (4, 7), (7, 10), (10, 14))
        ]
        expected = [170.0, 250.0, 335.0, 425.0, 505.0]
        self.assertTrue(all(abs(actual - target) < 20.0 for actual, target in zip(group_centers, expected)))

    def test_parallax_uses_one_global_seventy_five_percent_multiplier(self) -> None:
        self.assertIn("pace_multiplier: float = 1.75", self.parallax)
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
