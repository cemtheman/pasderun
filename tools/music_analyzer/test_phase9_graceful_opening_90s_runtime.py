from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_90 = ROOT / "scenes/gameplay/generated/graceful_opening_00_90_runtime.tscn"
RUNTIME_60 = ROOT / "scenes/gameplay/generated/graceful_opening_00_60_runtime.tscn"
PLAN_90 = ROOT / "data/geometry/graceful_opening_00_90_climax_fork.geometry_plan_v0_1.json"
PROJECT = ROOT / "project.godot"


class Phase9GracefulOpening90sRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME_90.read_text(encoding="utf-8")
        cls.runtime_60 = RUNTIME_60.read_text(encoding="utf-8")
        cls.plan = json.loads(PLAN_90.read_text(encoding="utf-8"))
        cls.project = PROJECT.read_text(encoding="utf-8")

    def test_90s_runtime_is_separate_and_uses_90s_artifacts(self) -> None:
        self.assertIn('name="GracefulOpening0090Runtime"', self.runtime)
        self.assertIn(
            'path="res://scenes/gameplay/generated/graceful_opening_00_90_climax_fork.tscn"',
            self.runtime,
        )
        self.assertIn(
            'geometry_plan_path = "res://data/geometry/graceful_opening_00_90_climax_fork.geometry_plan_v0_1.json"',
            self.runtime,
        )
        self.assertIn('name="GracefulOpening0060Runtime"', self.runtime_60)

    def test_completion_is_exactly_90_seconds(self) -> None:
        match = re.search(
            r'\[node name="SliceCompletion".*?position = Vector3\(([^,]+),\s*([^,]+),',
            self.runtime,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        completion_x = float(match.group(1))
        self.assertAlmostEqual(completion_x / 4.0, 90.0, places=4)
        self.assertEqual(float(match.group(2)), -2.8)

    def test_60_to_90_gameplay_sequence_is_present_in_runtime_plan(self) -> None:
        events = {
            float(event["source_time"]): event
            for event in self.plan["events"]
            if 60.0 <= float(event["source_time"]) < 90.0
        }
        self.assertEqual(
            sorted(events),
            [60.604, 68.5, 74.118, 82.75, 87.353],
        )
        self.assertEqual(events[60.604]["geometry"]["type"], "SMALL_GAP")
        self.assertEqual(events[68.5]["geometry"]["type"], "ROUTE_FORK")
        self.assertEqual(events[74.118]["geometry"]["type"], "SMALL_GAP")
        self.assertEqual(events[82.75]["geometry"]["type"], "ROUTE_FORK")
        self.assertEqual(events[87.353]["geometry"]["type"], "SMALL_GAP")

    def test_extension_forks_preserve_single_input_selection(self) -> None:
        for time in (68.5, 82.75):
            branch = next(
                event["branch"]
                for event in self.plan["events"]
                if float(event["source_time"]) == time
            )
            self.assertEqual(branch["split"]["jump_destination"], "TECHNICAL")
            self.assertEqual(branch["split"]["no_jump_destination"], "SAFE")
            self.assertEqual(
                branch["selection"],
                "no jump drops to LOWER SAFE; one climax jump reaches UPPER TECHNICAL",
            )

    def test_music_body_flow_hud_and_recovery_layers_are_preserved(self) -> None:
        for token in (
            'script = ExtResource("23_choreo")',
            'script = ExtResource("9_flow")',
            'script = ExtResource("21_recovery")',
            'name="DebugHUD"',
            'name="TapTimingDebug"',
            'name="AccentRuntimeTrace"',
            'tap_accents_require_accent_action = true',
        ):
            self.assertIn(token, self.runtime)

    def test_project_launches_90s_runtime(self) -> None:
        self.assertIn(
            'run/main_scene="res://scenes/gameplay/generated/graceful_opening_00_90_runtime.tscn"',
            self.project,
        )
        self.assertNotIn(
            'run/main_scene="res://scenes/gameplay/generated/graceful_opening_00_60_runtime.tscn"',
            self.project,
        )


if __name__ == "__main__":
    unittest.main()
