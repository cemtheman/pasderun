from __future__ import annotations

import json
import math
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COURSE = ROOT / "scenes/gameplay/generated/continuous_technical_course.tscn"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
RECOVERY = ROOT / "scenes/gameplay/run_recovery_manager.gd"
ANALYSIS = ROOT / "data/music/graceful_opening.analysis.json"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
PARALLAX = ROOT / "scenes/gameplay/parallax_presentation.gd"


class LevelFinaleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.course = COURSE.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.recovery = RECOVERY.read_text(encoding="utf-8")
        cls.analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
        cls.dancer = DANCER.read_text(encoding="utf-8")
        cls.parallax = PARALLAX.read_text(encoding="utf-8")

    def test_completion_threshold_matches_music_end_without_silent_run(self) -> None:
        duration = float(self.analysis["source"]["duration_seconds"])
        trigger_x = float(re.search(
            r'\[node name="LevelCompleteTrigger".*?position = Vector3\(([0-9.]+),',
            self.course,
            re.DOTALL,
        ).group(1))
        self.assertTrue(math.isclose(trigger_x, 560.0, abs_tol=0.001))
        self.assertLessEqual(abs(duration - trigger_x / 4.0), 0.05)
        self.assertLessEqual(max(0.0, trigger_x / 4.0 - duration), 0.05)

    def test_final_surface_is_short_stable_and_curtain_has_no_collision(self) -> None:
        self.assertIn('size = Vector3(17, 0.5, 4)', self.course)
        self.assertIn('position = Vector3(553.5, -3.05, 0)', self.course)
        self.assertIn('name="BackstageWingCurtain" type="MeshInstance3D"', self.course)
        self.assertNotIn('parent="Level/BackstageWingCurtain"', self.course)
        final_approach_seconds = (560.0 - 545.0) / 4.0
        self.assertGreaterEqual(final_approach_seconds, 3.0)
        self.assertLessEqual(final_approach_seconds, 5.0)

    def test_completion_is_distinct_and_has_priority_over_death(self) -> None:
        self.assertIn("LEVEL_COMPLETE", self.recovery)
        physics = re.search(r"func _physics_process\(.*?(?=\n\nfunc )", self.recovery, re.DOTALL).group(0)
        self.assertLess(
            physics.index("completion_trigger.global_position.x"),
            physics.index("DEATH_Y"),
        )
        self.assertIn("_state = RunState.LEVEL_COMPLETE", self.recovery)
        self.assertIn("if not _run_started or _state != RunState.PLAYING:", physics)

    def test_level_complete_overlay_is_independent_and_exact(self) -> None:
        self.assertIn('name="LevelCompleteOverlay" type="CanvasLayer" parent="."', self.runtime)
        self.assertNotIn('parent="DebugHUD/LevelCompleteOverlay"', self.runtime)
        self.assertIn('text = "LEVEL COMPLETE"', self.runtime)
        self.assertIn('text = "NEXT LEVEL"', self.runtime)
        self.assertIn('text = "MAIN MENU"', self.runtime)
        completion_block = self.runtime.split('[node name="LevelCompleteOverlay"', 1)[1]
        self.assertNotIn('text = "CONTINUE"', completion_block)
        self.assertNotIn('text = "RESTART"', completion_block)
        self.assertNotIn('text = "EXIT"', completion_block)

    def test_completion_stops_runtime_and_safe_next_level_fallback_is_explicit(self) -> None:
        complete = re.search(r"func _enter_level_complete_state\(.*?(?=\n\nfunc )", self.recovery, re.DOTALL).group(0)
        for expected in (
            "dancer.process_mode = Node.PROCESS_MODE_DISABLED",
            "audio_player.stop()",
            "music_root.process_mode = Node.PROCESS_MODE_DISABLED",
            "camera_rig.process_mode = Node.PROCESS_MODE_DISABLED",
            "level_complete_overlay.visible = true",
        ):
            self.assertIn(expected, complete)
        self.assertIn("next_level_button.disabled = next_level_scene == null", self.recovery)
        self.assertIn("get_tree().change_scene_to_packed(next_level_scene)", self.recovery)
        self.assertIn("func _return_to_main_menu()", self.recovery)
        self.assertIn("get_tree().reload_current_scene()", self.recovery)

    def test_checkpoint_and_existing_game_over_contract_remain(self) -> None:
        self.assertIn('{"id": "POST_FORK_05", "x": 535.0}', self.recovery)
        self.assertLess(535.0, 560.0)
        for label in ("GAME OVER", "CONTINUE", "RESTART", "EXIT"):
            self.assertIn(f'text = "{label}"', self.runtime)
        self.assertIn("const DEATH_Y := -6.0", self.recovery)
        self.assertIn("func _continue_from_checkpoint()", self.recovery)

    def test_gameplay_and_parallax_constants_are_unchanged(self) -> None:
        self.assertIn("@export var run_speed: float = 4.0", self.dancer)
        self.assertIn("@export var jump_velocity: float = 6.0", self.dancer)
        self.assertIn("@export var gravity: float = 18.0", self.dancer)
        self.assertIn("pace_multiplier: float = 2.50", self.parallax)


if __name__ == "__main__":
    unittest.main()
