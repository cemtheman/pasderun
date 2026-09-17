from __future__ import annotations

import math
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
COURSE = ROOT / "scenes/gameplay/generated/continuous_technical_course.tscn"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
FORK_CAMERA = ROOT / "scenes/gameplay/fork_camera_controller.gd"
RECOVERY = ROOT / "scenes/gameplay/run_recovery_manager.gd"
CAMERA_RIG = ROOT / "scenes/gameplay/camera_rig.gd"


class ForkCameraContinueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.course = COURSE.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")
        cls.camera = FORK_CAMERA.read_text(encoding="utf-8")
        cls.recovery = RECOVERY.read_text(encoding="utf-8")
        cls.camera_rig = CAMERA_RIG.read_text(encoding="utf-8")

    def test_five_explicit_ordered_fork_regions_have_route_bounds(self) -> None:
        self.assertEqual(self.course.count("metadata/fork_id = "), 5)
        for index in range(1, 6):
            block = re.search(
                rf'\[node name="RouteFork{index:02d}".*?(?=\n\[node )',
                self.course,
                re.DOTALL,
            ).group(0)
            values = {
                key: float(re.search(rf"metadata/{key} = (-?[0-9.]+)", block).group(1))
                for key in ("start_x", "split_x", "merge_x", "end_x", "upper_max_y", "lower_min_y")
            }
            self.assertLess(values["start_x"], values["split_x"])
            self.assertLess(values["split_x"], values["merge_x"])
            self.assertLess(values["merge_x"], values["end_x"])
            self.assertGreater(values["upper_max_y"], values["lower_min_y"])
            for marker in ("ForkStart", "RouteSplit", "ForkMerge", "ForkEnd"):
                self.assertIn(f'name="{marker}{index:02d}"', self.course)

    def test_safe_jump_envelope_has_clear_upper_corridor(self) -> None:
        safe_surface = -2.8
        capsule_height = 2.0
        jump_apex = 6.0**2 / (2.0 * 18.0)
        swept_top = safe_surface + capsule_height + jump_apex
        upper_centers = [
            float(value)
            for value in re.findall(
                r'\[node name="TechnicalRoute[^"]+" type="StaticBody3D" parent="Level"\]\n'
                r'position = Vector3\([0-9.]+, (-?[0-9.]+), 0\)',
                self.course,
            )
        ]
        self.assertEqual(len(upper_centers), 8)
        clearances = [(center - 0.25) - swept_top for center in upper_centers]
        self.assertTrue(math.isclose(min(clearances), 0.25, abs_tol=0.001))
        self.assertEqual(self.course.count("rotation = Vector3(0, 0, 0.26166)"), 5)

    def test_production_camera_caches_metadata_and_only_interpolates_per_frame(self) -> None:
        self.assertIn("func _collect_fork_metadata()", self.camera)
        process = re.search(r"func _process\(.*?(?=\n\nfunc )", self.camera, re.DOTALL).group(0)
        self.assertNotIn("get_children", process)
        self.assertNotIn("get_node", process)
        self.assertNotIn(".new()", process)
        self.assertIn("lerpf(camera.size", process)
        self.assertIn("route_center_y", process)
        self.assertIn("camera_rig.global_position.y = lerpf", process)
        self.assertIn("NORMAL_CAMERA_SIZE := 7.5", self.camera)
        self.assertIn("NORMAL_LOOK_AHEAD := 1.75", self.camera)
        self.assertIn('name="ProductionForkCamera"', self.runtime)

    def test_checkpoint_policy_is_forward_safe_and_outside_forks(self) -> None:
        self.assertIn('if not dancer.is_on_floor() or bool(dancer.get("has_fallen")):', self.recovery)
        self.assertIn('if not bool(fork_camera_controller.call("is_outside_fork")):', self.recovery)
        self.assertIn("_checkpoint_index = next_index", self.recovery)
        self.assertIn('_checkpoint_music_time = float(candidate["x"]) / RUN_SPEED', self.recovery)
        checkpoint_x = [float(v) for v in re.findall(r'"x": ([0-9.]+)', self.recovery)]
        self.assertEqual(checkpoint_x, [0.0, 201.0, 276.0, 356.0, 436.0, 535.0])
        self.assertEqual(checkpoint_x, sorted(checkpoint_x))

    def test_death_continue_restart_exit_and_policy_are_explicit(self) -> None:
        self.assertIn("const DEATH_Y := -6.0", self.recovery)
        self.assertIn("if dancer.global_position.y < DEATH_Y:", self.recovery)
        self.assertIn("if _dead", self.recovery)
        self.assertIn("audio_player.stop()", self.recovery)
        self.assertIn("audio_player.play(_checkpoint_music_time)", self.recovery)
        self.assertIn("get_tree().reload_current_scene()", self.recovery)
        self.assertIn('OS.has_feature("web")', self.recovery)
        self.assertIn("get_tree().quit()", self.recovery)
        self.assertIn("func continue_is_allowed()", self.recovery)
        self.assertIn("return true", self.recovery)
        self.assertIn("func continue_cost()", self.recovery)
        self.assertIn("return 0", self.recovery)

    def test_game_over_is_separate_from_debug_hud_and_has_exact_actions(self) -> None:
        self.assertIn('name="GameOverOverlay" type="CanvasLayer" parent="."', self.runtime)
        self.assertNotIn('parent="DebugHUD/GameOverOverlay"', self.runtime)
        for label in ("GAME OVER", "CONTINUE", "RESTART", "EXIT"):
            self.assertIn(f'text = "{label}"', self.runtime)

    def test_existing_debug_controls_and_web_label_guard_remain(self) -> None:
        probe = (ROOT / "scenes/gameplay/spatial_stall_probe.gd").read_text(encoding="utf-8")
        labels = (ROOT / "scenes/gameplay/generated/fork_debug_visualization.gd").read_text(encoding="utf-8")
        for key in ('KEY_F', 'KEY_V', 'KEY_B'):
            self.assertIn(key, probe)
        self.assertIn('OS.has_feature("web")', labels)
        self.assertIn("look_ahead: float = 1.75", self.camera_rig)


if __name__ == "__main__":
    unittest.main()
