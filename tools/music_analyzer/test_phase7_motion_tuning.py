from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "scenes/gameplay/dancer_visual_motion_v2.gd"
POLISH = ROOT / "scenes/gameplay/dancer_visual_motion_v3.gd"
FINAL = ROOT / "scenes/gameplay/dancer_visual_motion_v4.gd"
TAP = ROOT / "scenes/gameplay/dancer_tap_feedback.gd"
BOOTSTRAP = ROOT / "scenes/gameplay/dancer_visual_bootstrap.gd"


class Phase7MotionTuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.run = RUN.read_text(encoding="utf-8")
        cls.polish = POLISH.read_text(encoding="utf-8")
        cls.final = FINAL.read_text(encoding="utf-8")
        cls.tap = TAP.read_text(encoding="utf-8")
        cls.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")

    def test_motion_layers_are_visual_only(self) -> None:
        self.assertIn('extends "res://scenes/gameplay/dancer_visual.gd"', self.run)
        self.assertIn('extends "res://scenes/gameplay/dancer_visual_motion_v2.gd"', self.polish)
        self.assertIn('extends "res://scenes/gameplay/dancer_visual_motion_v3.gd"', self.final)
        for source in (self.run, self.polish, self.final):
            for forbidden in ('velocity =', 'global_position =', 'move_and_slide()', 'move_and_collide('):
                self.assertNotIn(forbidden, source)

    def test_travel_uses_alternating_ballerina_run_weight_transfer(self) -> None:
        for pose in (
            'func _front_contact_pose()',
            'func _back_brush_pose()',
            'func _back_flight_pose()',
            'func _back_contact_pose()',
            'func _front_brush_pose()',
            'func _front_flight_pose()',
        ):
            self.assertIn(pose, self.run)
        self.assertIn('RUN_CYCLE_DURATION := 0.56', self.run)
        self.assertIn('RUN_FLIGHT_LIFT := 0.048', self.run)

    def test_landing_continues_into_next_running_step(self) -> None:
        self.assertIn('func _landing_animation()', self.final)
        self.assertIn('[0.0, 0.055, 0.125, 0.185, 0.22]', self.final)
        self.assertIn('_landing_catch_pose()', self.final)
        self.assertIn('_back_brush_pose()', self.final)
        self.assertIn('_back_contact_pose()', self.final)
        self.assertIn('_front_brush_pose()', self.final)
        self.assertIn('from_state == STATE_LANDING and to_state == STATE_TRAVEL', self.final)
        self.assertIn('return 0.02', self.final)

    def test_recovery_uses_small_rebound_before_run(self) -> None:
        self.assertIn('func _stumble_animation()', self.final)
        self.assertIn('func _recovery_animation()', self.final)
        self.assertIn('func _recovery_hop_pose()', self.final)
        self.assertIn('Vector3(0.0, 0.052, 0.0)', self.final)
        self.assertIn('_animation_from_poses(0.62, [0.0, 0.10, 0.22, 0.36, 0.50, 0.62]', self.final)
        self.assertIn('from_state == STATE_STUMBLE and to_state == STATE_RECOVERY', self.final)
        self.assertIn('from_state == STATE_RECOVERY and to_state == STATE_TRAVEL', self.final)

    def test_low_transition_and_balance_polish_remain(self) -> None:
        self.assertIn('func _low_transition_animation()', self.polish)
        self.assertIn('func _low_run_pose(', self.polish)
        self.assertIn('func _balance_animation()', self.polish)
        self.assertIn('func _retire_balance_pose(', self.polish)

    def test_tap_response_is_presentation_only(self) -> None:
        self.assertIn('tap_detected', self.tap)
        self.assertIn('TorusMesh.new()', self.tap)
        self.assertIn('PULSE_DURATION := 0.18', self.tap)
        for forbidden in ('velocity =', 'global_position =', 'move_and_slide()', 'move_and_collide('):
            self.assertNotIn(forbidden, self.tap)

    def test_bootstrap_uses_final_motion_layer_and_tap_feedback(self) -> None:
        self.assertIn('dancer_visual_motion_v4.gd', self.bootstrap)
        self.assertIn('dancer_tap_feedback.gd', self.bootstrap)
        self.assertIn('TapVisualFeedback', self.bootstrap)
        self.assertIn('capsule_visual.visible = false', self.bootstrap)


if __name__ == "__main__":
    unittest.main()
