from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_120 = ROOT / "scenes/gameplay/generated/graceful_opening_00_120_runtime.tscn"
RUNTIME_90 = ROOT / "scenes/gameplay/generated/graceful_opening_00_90_runtime.tscn"
PLAN = ROOT / "data/geometry/graceful_opening_00_120_topology_v1_1.geometry_plan_v0_1.json"
PROJECT = ROOT / "project.godot"


class Phase9GracefulOpening120sRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME_120.read_text(encoding="utf-8")
        cls.runtime_90 = RUNTIME_90.read_text(encoding="utf-8")
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        cls.project = PROJECT.read_text(encoding="utf-8")
        cls.crest = next(
            event for event in cls.plan["events"]
            if float(event["source_time"]) == 68.5
        )
        cls.staircase = next(
            event for event in cls.plan["events"]
            if float(event["source_time"]) == 102.5
        )

    def test_120s_runtime_is_separate_and_uses_topology_v1_1_artifacts(self) -> None:
        self.assertIn('name="GracefulOpening0120Runtime"', self.runtime)
        self.assertIn(
            'path="res://scenes/gameplay/generated/graceful_opening_00_120_topology_v1_1.tscn"',
            self.runtime,
        )
        self.assertIn(
            'geometry_plan_path = "res://data/geometry/graceful_opening_00_120_topology_v1_1.geometry_plan_v0_1.json"',
            self.runtime,
        )
        self.assertIn('name="GracefulOpening0090Runtime"', self.runtime_90)

    def test_completion_is_exactly_120_seconds(self) -> None:
        match = re.search(
            r'\[node name="SliceCompletion".*?position = Vector3\(([^,]+),\s*([^,]+),',
            self.runtime,
            re.DOTALL,
        )
        self.assertIsNotNone(match)
        self.assertAlmostEqual(float(match.group(1)) / 4.0, 120.0, places=4)
        self.assertEqual(float(match.group(2)), -2.8)

    def test_685_runtime_event_is_crest(self) -> None:
        branch = self.crest["branch"]
        self.assertEqual(branch["topology"], "CREST")
        self.assertEqual(branch["routes"]["technical"]["profile"], "STEPPED_CREST")
        terraces = [
            segment
            for segment in branch["routes"]["technical"]["segments"]
            if str(segment["type"]).startswith("CREST_TERRACE_")
        ]
        self.assertEqual(
            [float(segment["surface_y"]) for segment in terraces],
            [0.0, 0.28, 0.56, 0.28, 0.0],
        )
        self.assertFalse(branch["new_required_actions"])

    def test_1025_runtime_event_is_crescendo_staircase(self) -> None:
        branch = self.staircase["branch"]
        self.assertEqual(branch["topology"], "CRESCENDO_STAIRCASE")
        self.assertEqual(branch["split"]["jump_destination"], "TECHNICAL")
        self.assertEqual(branch["split"]["no_jump_destination"], "SAFE")
        self.assertEqual(
            branch["routes"]["technical"]["failure_policy"],
            "FAIL_DOWN_TO_SAFE",
        )

    def test_staircase_has_four_rising_steps_and_three_optional_gaps(self) -> None:
        segments = self.staircase["branch"]["routes"]["technical"]["segments"]
        steps = [
            segment for segment in segments
            if str(segment["type"]).startswith("STAIR_STEP_")
        ]
        gaps = [
            segment for segment in segments
            if str(segment["type"]).startswith("STEP_GAP_")
        ]
        self.assertEqual(
            [float(segment["surface_y"]) for segment in steps],
            [0.0, 0.28, 0.56, 0.84],
        )
        self.assertEqual(len(gaps), 3)
        self.assertTrue(all(
            segment["optional_mastery_action"] == "JUMP"
            and segment["failure_destination"] == "SAFE"
            for segment in gaps
        ))

    def test_runtime_preserves_body_flow_debug_and_recovery_layers(self) -> None:
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

    def test_120s_runtime_remains_available_as_rollback_baseline(self) -> None:
        self.assertIn('name="GracefulOpening0120Runtime"', self.runtime)
        self.assertIn(
            'path="res://scenes/gameplay/generated/graceful_opening_00_120_topology_v1_1.tscn"',
            self.runtime,
        )
        self.assertNotIn(
            'graceful_opening_00_140_bridge.tscn',
            self.runtime,
        )


if __name__ == "__main__":
    unittest.main()
