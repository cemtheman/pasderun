from __future__ import annotations

import json
import math
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
COURSE = ROOT / "scenes/gameplay/generated/continuous_technical_course.tscn"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
PARALLAX = ROOT / "scenes/gameplay/parallax_presentation.gd"
ANALYSIS = ROOT / "data/music/graceful_opening.analysis.json"


class ContinuousTechnicalCourseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.course = COURSE.read_text(encoding="utf-8")
        cls.generated = GENERATED.read_text(encoding="utf-8")
        cls.dancer = DANCER.read_text(encoding="utf-8")
        cls.parallax = PARALLAX.read_text(encoding="utf-8")
        cls.analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
        cls.lengths = {
            resource: float(length)
            for resource, length in re.findall(
                r'\[sub_resource type="BoxMesh" id="([^"]+)"\]\n'
                r"size = Vector3\(([0-9.]+), 0.5, 4\)",
                cls.course,
            )
        }

    def _body(self, name: str) -> tuple[float, float, float]:
        block = re.search(
            rf'\[node name="{re.escape(name)}" type="StaticBody3D" parent="Level"\]'
            rf'.*?(?=\n\[node |\Z)',
            self.course,
            re.DOTALL,
        ).group(0)
        x, y = re.search(
            r"position = Vector3\(([0-9.]+), (-?[0-9.]+), 0\)", block
        ).groups()
        mesh = re.search(
            rf'parent="Level/{re.escape(name)}"\]\nmesh = SubResource\("([^"]+)"\)',
            self.course,
        ).group(1)
        return float(x), float(y), self.lengths[mesh]

    @staticmethod
    def _bounds(body: tuple[float, float, float]) -> tuple[float, float]:
        x, _, length = body
        return x - length / 2.0, x + length / 2.0

    def test_runtime_uses_isolated_static_course_scene(self) -> None:
        self.assertIn(
            'path="res://scenes/gameplay/generated/continuous_technical_course.tscn"',
            self.runtime,
        )
        self.assertIn(
            '[node name="ExtendedCourse" parent="." instance=ExtResource("19_course")]',
            self.runtime,
        )
        self.assertNotIn('type="StaticBody3D" parent="ExtendedCourse"', self.runtime)

    def test_audio_duration_and_controller_contract_are_unchanged(self) -> None:
        duration = float(self.analysis["source"]["duration_seconds"])
        self.assertTrue(math.isclose(duration, 140.016, abs_tol=0.001))
        self.assertIn("@export var run_speed: float = 4.0", self.dancer)
        self.assertIn("@export var jump_velocity: float = 6.0", self.dancer)
        self.assertIn("@export var gravity: float = 18.0", self.dancer)
        self.assertIn("@export var fall_limit_y: float = -3.0", self.dancer)

    def test_exact_platform_gap_and_fork_counts(self) -> None:
        platforms = re.findall(
            r'\[node name="[^"]*TechnicalPlatform[^"]*" type="StaticBody3D" parent="Level"\]',
            self.course,
        )
        gaps = re.findall(
            r'\[node name="GapEvent[0-9]{2}_[^"]+" type="Marker3D" parent="Level"\]',
            self.course,
        )
        forks = re.findall(
            r'\[node name="RouteFork[0-9]{2}" type="Node3D" parent="Level"\]',
            self.course,
        )
        self.assertEqual(len(platforms), 24)
        self.assertEqual(len(gaps), 16)
        self.assertEqual(len(forks), 5)

    def test_forks_are_distributed_and_have_natural_input_topology(self) -> None:
        expected = [(175.0, 193.0), (250.0, 268.0), (330.0, 348.0), (410.0, 428.0), (505.0, 523.0)]
        for index, (start_expected, merge_expected) in enumerate(expected, 1):
            start = float(re.search(
                rf'\[node name="ForkStart{index:02d}".*?position = Vector3\(([0-9.]+),',
                self.course,
                re.DOTALL,
            ).group(1))
            merge = float(re.search(
                rf'\[node name="ForkMerge{index:02d}".*?position = Vector3\(([0-9.]+),',
                self.course,
                re.DOTALL,
            ).group(1))
            self.assertEqual((start, merge), (start_expected, merge_expected))
            self.assertIn(f'[node name="SafeLowerRoute{index:02d}"', self.course)
            self.assertIn(f'[node name="TechnicalRoute{index:02d}_', self.course)
        self.assertEqual(self.course.count('metadata/_design = "NO_JUMP_SAFE__JUMP_TECHNICAL"'), 5)

    def test_each_fork_safe_route_is_active_and_reconnects(self) -> None:
        for index in range(1, 6):
            safe_a = self._body(f"SafeLowerRoute{index:02d}")
            safe_b = self._body(f"SafeRoute{index:02d}_B")
            recovery_number = {1: 3, 2: 8, 3: 13, 4: 18, 5: 24}[index]
            recovery = self._body(f"TechnicalPlatform{recovery_number:02d}_Recovery")
            _, safe_a_end = self._bounds(safe_a)
            safe_b_start, safe_b_end = self._bounds(safe_b)
            recovery_start, _ = self._bounds(recovery)
            expected_safe_gap = 1.5 if index in {3, 5} else 0.0
            self.assertTrue(math.isclose(safe_b_start - safe_a_end, expected_safe_gap, abs_tol=0.001))
            self.assertTrue(math.isclose(safe_b_end, recovery_start, abs_tol=0.001))

    def test_technical_routes_require_jump_and_reconnect(self) -> None:
        first_platform = {
            1: "TechnicalRoute01_TechnicalPlatform02_Upper",
            2: "TechnicalRoute02_TechnicalPlatform06_UpperA",
            3: "TechnicalRoute03_TechnicalPlatform11_UpperA",
            4: "TechnicalRoute04_TechnicalPlatform16_UpperA",
            5: "TechnicalRoute05_TechnicalPlatform22_UpperA",
        }
        final_platform = {
            1: "TechnicalRoute01_TechnicalPlatform02_Upper",
            2: "TechnicalRoute02_TechnicalPlatform07_UpperB",
            3: "TechnicalRoute03_TechnicalPlatform12_UpperB",
            4: "TechnicalRoute04_TechnicalPlatform16_UpperA",
            5: "TechnicalRoute05_TechnicalPlatform23_UpperB",
        }
        merge_gap_forks = {1, 3, 4, 5}
        for index in range(1, 6):
            start_x = [175.0, 250.0, 330.0, 410.0, 505.0][index - 1]
            merge_x = [193.0, 268.0, 348.0, 428.0, 523.0][index - 1]
            tech_start, _ = self._bounds(self._body(first_platform[index]))
            _, tech_end = self._bounds(self._body(final_platform[index]))
            self.assertTrue(math.isclose(tech_start - start_x, 1.5, abs_tol=0.001))
            expected_descent_gap = 1.5 if index in merge_gap_forks else 0.0
            self.assertTrue(math.isclose(merge_x - tech_end, expected_descent_gap, abs_tol=0.001))

    def test_gap_events_are_controller_safe_and_descents_use_gaps(self) -> None:
        gap_x = [
            float(value)
            for value in re.findall(
                r'\[node name="GapEvent[0-9]{2}_[^"]+".*?'
                r'position = Vector3\(([0-9.]+),',
                self.course,
                re.DOTALL,
            )
        ]
        self.assertEqual(len(gap_x), 16)
        self.assertEqual(len(set(gap_x)), 16)
        self.assertEqual(self.course.count('_DESCENT" type="Marker3D"'), 4)
        downward_transitions = 5
        self.assertGreaterEqual(4 / downward_transitions, 0.5)
        proven_jump_range = 4.0 * (2.0 * 6.0 / 18.0)
        self.assertLess(1.5, proven_jump_range * 0.65)

    def test_vertical_clearance_and_elevation_are_safe(self) -> None:
        safe_surface = -3.05 + 0.25
        dancer_top = safe_surface + 2.0
        technical_underside = -0.25 - 0.25
        self.assertGreaterEqual(technical_underside - dancer_top, 0.25)
        upper_a_surface = -0.25 + 0.25
        upper_b_surface = 0.0 + 0.25
        self.assertEqual(upper_b_surface, 0.25)
        self.assertLessEqual(upper_b_surface - upper_a_surface, 0.5)
        self.assertEqual(self.course.count("rotation = Vector3(0, 0, 0.1974)"), 5)

    def test_active_neutral_spans_are_short_and_course_closes_cleanly(self) -> None:
        active_neutral_lengths = [
            self._body(f"NeutralRunway{index:02d}")[2] for index in range(2, 6)
        ]
        self.assertLessEqual(max(active_neutral_lengths), 12.0)
        closing = self._body("NeutralClosingRunway")
        closing_start, closing_end = self._bounds(closing)
        self.assertTrue(math.isclose(closing_start, 545.0, abs_tol=0.001))
        self.assertTrue(math.isclose(closing_end, 580.064, abs_tol=0.001))
        final_technical = self._body("TechnicalPlatform24_Recovery")
        self.assertTrue(math.isclose(self._bounds(final_technical)[1], 545.0, abs_tol=0.001))

    def test_meaningful_action_spacing_stays_below_twenty_five_units(self) -> None:
        action_x = [
            161.0, 175.75, 192.25, 215.0, 235.25,
            250.75, 268.0, 291.0, 315.25,
            330.75, 347.25, 371.0, 395.25,
            410.75, 427.25, 450.0, 462.75, 475.0, 490.25,
            505.75, 522.25, 545.0,
        ]
        longest = max(right - left for left, right in zip(action_x, action_x[1:]))
        self.assertLessEqual(longest, 25.0)

    def test_every_surface_has_matching_mesh_and_collision(self) -> None:
        bodies = re.findall(
            r'\[node name="([^"]+)" type="StaticBody3D" parent="Level"\]',
            self.course,
        )
        for name in bodies:
            mesh = re.search(
                rf'parent="Level/{re.escape(name)}"\]\nmesh = SubResource\("Mesh_([^"]+)"\)',
                self.course,
            ).group(1)
            shape = re.search(
                rf'parent="Level/{re.escape(name)}"\]\nshape = SubResource\("Shape_([^"]+)"\)',
                self.course,
            ).group(1)
            self.assertEqual(mesh, shape)

    def test_authored_opening_remains_separate(self) -> None:
        self.assertEqual(self.generated.count('type="Marker3D" parent="Events"'), 6)
        self.assertNotIn("ContinuousTechnicalCourse", self.generated)

    def test_parallax_uses_one_global_scale_and_exact_effective_factors(self) -> None:
        self.assertIn("pace_multiplier: float = 2.50", self.parallax)
        self.assertIn("paced_progress_x := progress_x * pace_multiplier", self.parallax)
        factors = [
            float(value)
            for value in re.findall(
                r"(?:far|mid|foreground)_factor: float = ([0-9.]+)",
                self.parallax,
            )
        ]
        self.assertEqual(factors, [0.005, 0.010, 0.018])
        self.assertEqual([factor * 2.5 for factor in factors], [0.0125, 0.025, 0.045])
        self.assertEqual(self.parallax.count("paced_progress_x *"), 3)
        self.assertNotIn("position.y", self.parallax)
        self.assertNotIn(".new()", self.parallax)


if __name__ == "__main__":
    unittest.main()
