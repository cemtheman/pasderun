from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_60 = ROOT / "scenes/gameplay/generated/graceful_opening_00_60_runtime.tscn"
RUNTIME_30 = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
FRAMING = ROOT / "scenes/gameplay/generated/fork_camera_framing.gd"
RECOVERY = ROOT / "scenes/gameplay/run_recovery_manager.gd"
PROJECT = ROOT / "project.godot"


class Phase9GracefulOpening60sRuntimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.runtime = RUNTIME_60.read_text(encoding="utf-8")
        cls.baseline_runtime = RUNTIME_30.read_text(encoding="utf-8")
        cls.framing = FRAMING.read_text(encoding="utf-8")
        cls.recovery = RECOVERY.read_text(encoding="utf-8")
        cls.project = PROJECT.read_text(encoding="utf-8")

    def test_60s_runtime_is_isolated_from_full_course_extension(self) -> None:
        self.assertIn(
            'path="res://scenes/gameplay/generated/graceful_opening_00_60_spatial.tscn"',
            self.runtime,
        )
        self.assertIn(
            'geometry_plan_path = "res://data/geometry/graceful_opening_00_60.geometry_plan_v0_1.json"',
            self.runtime,
        )
        self.assertIn(
            'path="res://scenes/gameplay/generated/graceful_opening_00_60_spatial.tscn"',
            self.runtime,
        )
        self.assertNotIn(
            'path="res://scenes/gameplay/generated/graceful_opening_00_60.tscn"',
            self.runtime,
        )
        self.assertNotIn("continuous_technical_course.tscn", self.runtime)
        self.assertNotIn('name="ExtendedCourse"', self.runtime)
        self.assertNotIn('name="ProductionForkCamera"', self.runtime)

    def test_completion_is_music_synchronous_at_exact_60_seconds(self) -> None:
        block = re.search(
            r'\[node name="SliceCompletion".*?position = Vector3\(([^,]+),\s*([^,]+),',
            self.runtime,
            re.DOTALL,
        )
        self.assertIsNotNone(block)
        completion_x = float(block.group(1))
        self.assertAlmostEqual(completion_x / 4.0, 60.0, places=4)
        self.assertEqual(float(block.group(2)), -2.8)
        self.assertIn('completion_trigger = NodePath("../SliceCompletion")', self.runtime)

    def test_generated_fork_framing_satisfies_recovery_controller_contract(self) -> None:
        for signature in (
            "func set_frozen(value: bool)",
            "func restore_normal_state()",
            "func is_outside_fork()",
        ):
            self.assertIn(signature, self.framing)
        self.assertIn("if _frozen or camera_rig == null", self.framing)
        self.assertIn(
            'fork_camera_controller = NodePath("../CameraRig/ForkFraming")',
            self.runtime,
        )
        for call in (
            'fork_camera_controller.call("set_frozen", true)',
            'fork_camera_controller.call("restore_normal_state")',
            'fork_camera_controller.call("is_outside_fork")',
        ):
            self.assertIn(call, self.recovery)

    def test_phase9_tap_markers_only_use_primary_accent_actions_after_opening(self) -> None:
        musicality = (ROOT / "scenes/gameplay/musicality.gd").read_text(encoding="utf-8")
        demands = __import__("json").loads(
            (ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json").read_text(encoding="utf-8")
        )
        self.assertIn("@export var tap_accents_require_accent_action := false", musicality)
        self.assertIn('tap_accents_require_accent_action = true', self.runtime)
        self.assertIn('String(primary_candidate.get("class", "")) != "ACCENT_ACTION"', musicality)

        phase9_tap_times = [
            float(event["time"])
            for event in demands["events"]
            if 30.0 < float(event["time"]) <= 60.0
            and event["candidate_classes"][0]["class"] == "ACCENT_ACTION"
        ]
        self.assertEqual(phase9_tap_times, [37.593, 43.862, 46.208, 50.62, 56.889])

        phase9_jump_times = [
            float(event["time"])
            for event in demands["events"]
            if 30.0 < float(event["time"]) <= 60.0
            and event["candidate_classes"][0]["class"] == "LARGE_TRAVELLING_LEAP"
        ]
        self.assertEqual(phase9_jump_times, [32.25, 36.25, 42.5, 53.0])


    def test_phase8_hud_and_timing_instrumentation_are_preserved(self) -> None:
        for node_name in (
            "DebugHUD",
            "PerformanceDebug",
            "AccentRuntimeTrace",
            "RuntimeStartGate",
            "MobileOrientationGate",
            "TapTimingDebug",
        ):
            self.assertIn(f'name="{node_name}"', self.runtime)


    def test_project_launches_phase9_60s_runtime(self) -> None:
        self.assertIn(
            'run/main_scene="res://scenes/gameplay/generated/graceful_opening_00_60_runtime.tscn"',
            self.project,
        )
        self.assertNotIn('run/main_scene="uid://wrse8kqkd211"', self.project)

    def test_accepted_30s_runtime_remains_full_course_baseline(self) -> None:
        self.assertIn("continuous_technical_course.tscn", self.baseline_runtime)
        self.assertIn('name="ExtendedCourse"', self.baseline_runtime)
        self.assertIn('name="ProductionForkCamera"', self.baseline_runtime)


if __name__ == "__main__":
    unittest.main()
