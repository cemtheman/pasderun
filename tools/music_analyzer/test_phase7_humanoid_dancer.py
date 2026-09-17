from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "project.godot"
VISUAL = ROOT / "scenes/gameplay/dancer_visual.gd"
BOOTSTRAP = ROOT / "scenes/gameplay/dancer_visual_bootstrap.gd"
DANCER = ROOT / "scenes/gameplay/dancer.gd"


class Phase7HumanoidDancerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project = PROJECT.read_text(encoding="utf-8")
        cls.visual = VISUAL.read_text(encoding="utf-8")
        cls.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
        cls.dancer = DANCER.read_text(encoding="utf-8")

    def test_visual_bootstrap_is_registered_without_touching_main_scene_contract(self) -> None:
        self.assertIn('[autoload]', self.project)
        self.assertIn('DancerVisualBootstrap="*res://scenes/gameplay/dancer_visual_bootstrap.gd"', self.project)
        self.assertIn('run/main_scene="uid://wrse8kqkd211"', self.project)

    def test_capsule_collision_is_not_removed_or_replaced(self) -> None:
        self.assertIn('CollisionShape3D', (ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn").read_text(encoding="utf-8"))
        self.assertNotIn('CollisionShape3D.new()', self.visual)
        self.assertIn('capsule_visual.visible = false', self.bootstrap)

    def test_articulated_humanoid_structure_exists(self) -> None:
        for part in (
            'Pelvis', 'Torso', 'Head',
            'ArmBackShoulder', 'ArmBackElbow',
            'ArmFrontShoulder', 'ArmFrontElbow',
            'LegBackHip', 'LegBackKnee', 'FootBack',
            'LegFrontHip', 'LegFrontKnee', 'FootFront',
        ):
            self.assertIn(part, self.visual)

    def test_animation_player_and_tree_are_runtime_owned_by_visual_layer(self) -> None:
        self.assertIn('AnimationPlayer.new()', self.visual)
        self.assertIn('AnimationTree.new()', self.visual)
        self.assertIn('AnimationNodeStateMachine.new()', self.visual)
        self.assertIn('_playback.travel(state)', self.visual)

    def test_required_visual_states_exist(self) -> None:
        for state in (
            'NEUTRAL', 'TRAVEL', 'JUMP', 'AIRBORNE', 'LANDING',
            'LOW_TRANSITION', 'BALANCE', 'STUMBLE', 'RECOVERY',
        ):
            self.assertIn(f'&"{state}"', self.visual)

    def test_visual_bridge_consumes_phase6_state_instead_of_redefining_it(self) -> None:
        self.assertIn('get_locomotion_state', self.visual)
        self.assertIn('locomotion == STATE_STUMBLE', self.visual)
        self.assertIn('locomotion == STATE_RECOVERY', self.visual)
        self.assertNotIn('_trigger_stumble', self.visual)
        self.assertNotIn('STUMBLE_DURATION', self.visual)
        self.assertNotIn('RECOVERY_DURATION', self.visual)

    def test_low_transition_and_balance_are_observed_not_reimplemented(self) -> None:
        self.assertIn('dancer.get("in_low_transition")', self.visual)
        self.assertIn('dancer.get("in_balance_zone")', self.visual)
        self.assertNotIn('capsule.height', self.visual)
        self.assertNotIn('balance_drift_speed', self.visual)

    def test_no_root_motion_or_global_gameplay_translation(self) -> None:
        forbidden = (
            'dancer.global_position =',
            'dancer.position =',
            'dancer.velocity =',
            'global_position =',
            'move_and_slide()',
            'move_and_collide(',
        )
        for token in forbidden:
            self.assertNotIn(token, self.visual)
        self.assertIn('"Rig:position"', self.visual)

    def test_phase6_gameplay_constants_remain_in_dancer(self) -> None:
        for contract in (
            'STUMBLE_DURATION := 0.24',
            'RECOVERY_DURATION := 0.62',
            'STUMBLE_SPEED_MULTIPLIER := 0.45',
            'RECOVERY_SPEED_MULTIPLIER := 1.21',
            '@export var run_speed: float = 4.0',
        ):
            self.assertIn(contract, self.dancer)

    def test_visual_state_logic_has_explicit_priority(self) -> None:
        resolver = re.search(r'func _resolve_visual_state\(.*?(?=\n\nfunc |\Z)', self.visual, re.DOTALL)
        self.assertIsNotNone(resolver)
        source = resolver.group(0)
        ordering = [
            'locomotion == STATE_STUMBLE',
            'locomotion == STATE_RECOVERY',
            'in_low_transition',
            'in_balance_zone',
            'not grounded',
            'STATE_LANDING',
            'STATE_TRAVEL',
        ]
        positions = [source.index(token) for token in ordering]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
