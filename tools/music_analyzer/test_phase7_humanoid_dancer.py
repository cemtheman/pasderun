from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "project.godot"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
CONTROLLER = ROOT / "scenes/characters/humanoid_motion_controller.gd"
BALLERINA = ROOT / "scenes/characters/ballerina_visual_v_1.tscn"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"


class Phase7HumanoidDancerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project = PROJECT.read_text(encoding="utf-8")
        cls.dancer = DANCER.read_text(encoding="utf-8")
        cls.controller = CONTROLLER.read_text(encoding="utf-8")
        cls.ballerina = BALLERINA.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_main_scene_and_collision_contract_remain(self) -> None:
        self.assertIn(
            'run/main_scene="res://scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"',
            self.project,
        )
        self.assertIn('CollisionShape3D', self.runtime)
        self.assertIn('CapsuleShape3D', self.runtime)
        self.assertIn(
            'path="res://scenes/characters/ballerina_visual_v_1.tscn"',
            self.runtime,
        )

    def test_phase6_gameplay_constants_remain_in_dancer(self) -> None:
        for contract in (
            'STUMBLE_DURATION := 0.36',
            'RECOVERY_DURATION := 0.72',
            'STUMBLE_SPEED_MULTIPLIER := 0.68',
            'RECOVERY_SPEED_MULTIPLIER := 1.05',
            '@export var run_speed: float = 4.0',
            'func get_locomotion_state() -> StringName:',
            'func get_last_landing_drop_distance() -> float:',
            'func get_last_landing_was_jump() -> bool:',
        ):
            self.assertIn(contract, self.dancer)

    def test_humanoid_visual_does_not_take_gameplay_translation(self) -> None:
        forbidden = (
            'move_and_slide()',
            'move_and_collide(',
            '_dancer.global_position =',
            '_dancer.position =',
            '_dancer.velocity =',
        )
        for token in forbidden:
            self.assertNotIn(token, self.controller)

    def test_visual_priority_keeps_air_and_landing_before_stumble(self) -> None:
        resolver = re.search(
            r'func _resolve_visual_state\(.*?(?=\n\nfunc |\Z)',
            self.controller,
            re.DOTALL,
        )
        self.assertIsNotNone(resolver)
        source = resolver.group(0)
        ordering = [
            'if not grounded:',
            'return STATE_AIRBORNE',
            'return STATE_LANDING',
            'if locomotion == STATE_STUMBLE:',
            'if locomotion == STATE_RECOVERY:',
        ]
        positions = [source.index(token) for token in ordering]
        self.assertEqual(positions, sorted(positions))

    def test_ballerina_scene_owns_the_single_humanoid_controller(self) -> None:
        self.assertIn(
            'path="res://scenes/characters/humanoid_motion_controller.gd"',
            self.ballerina,
        )
        self.assertNotIn('ballerina_motion_retarget', self.ballerina)
        self.assertNotIn('DancerVisualBootstrap', self.project)


if __name__ == "__main__":
    unittest.main()
