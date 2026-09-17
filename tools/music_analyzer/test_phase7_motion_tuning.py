from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "scenes/gameplay/dancer_visual_motion_v2.gd"
POLISH = ROOT / "scenes/gameplay/dancer_visual_motion_v3.gd"
FINAL = ROOT / "scenes/gameplay/dancer_visual_motion_v4.gd"
LOW = ROOT / "scenes/gameplay/dancer_visual_motion_v5.gd"
TAP = ROOT / "scenes/gameplay/dancer_tap_feedback.gd"
BOOTSTRAP = ROOT / "scenes/gameplay/dancer_visual_bootstrap.gd"


class Phase7MotionTuningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.run = RUN.read_text(encoding="utf-8")
        cls.polish = POLISH.read_text(encoding="utf-8")
        cls.final = FINAL.read_text(encoding="utf-8")
        cls.low = LOW.read_text(encoding="utf-8")
        cls.tap = TAP.read_text(encoding="utf-8")
        cls.bootstrap = BOOTSTRAP.read_text(encoding="utf-8")

    def test_motion_layers_are_visual_only(self) -> None:
        self.assertIn('extends "res://scenes/gameplay/dancer_visual.gd"', self.run)
        self.assertIn('extends "res://scenes/gameplay/dancer_visual_motion_v2.gd"', self.polish)
        self.assertIn('extends "res://scenes/gameplay/dancer_visual_motion_v3.gd"', self.final)
        self.assertIn('extends "res://scenes/gameplay/dancer_visual_motion_v4.gd"', self.low)
        for source in (self.run, self.polish, self.final, self.low):
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

    def test_low_transition_uses_anatomical_knee_flexion(self) -> None:
        self.assertIn('func _low_transition_animation()', self.low)
        self.assertIn('func _low_articulated_pose_v5(', self.low)
        self.assertIn('Vector3(0.020, depth, 0.0)', self.low)
        self.assertIn('0.38, -0.76, 0.36', self.low)
        self.assertIn('0.45, -0.90, 0.43', self.low)
        self.assertIn('-0.085', self.low)
        self.assertNotIn('-0.130', self.low)

    def test_low_transition_and_balance_polish_remain(self) -> None:
        self.assertIn('func _balance_animation()', self.polish)
        self.assertIn('func _retire_balance_pose(', self.polish)

    def test_tap_response_is_presentation_only_and_web_has_no_3d_pulse(self) -> None:
        self.assertIn('tap_detected', self.tap)
        self.assertIn('OS.has_feature("web")', self.tap)
        self.assertIn('WEB_PULSE_DURATION := 0.12', self.tap)
        self.assertIn('WEB_SCALE_AMOUNT := 0.018', self.tap)
        self.assertIn('_web_visual.scale', self.tap)
        self.assertIn('if _web_mode:', self.tap)
        self.assertIn('else:\n\t\t_build_ring()', self.tap)
        self.assertIn('TorusMesh.new()', self.tap)
        self.assertNotIn('transparency', self.tap)
        self.assertNotIn('emission_enabled', self.tap)
        self.assertNotIn('emission_energy_multiplier', self.tap)
        for forbidden in ('velocity =', 'global_position =', 'move_and_slide()', 'move_and_collide('):
            self.assertNotIn(forbidden, self.tap)

    def test_bootstrap_uses_final_motion_layer_and_tap_feedback(self) -> None:
        self.assertIn('dancer_visual_motion_v5.gd', self.bootstrap)
        self.assertIn('dancer_tap_feedback.gd', self.bootstrap)
        self.assertIn('TapVisualFeedback', self.bootstrap)
        self.assertIn('capsule_visual.visible = false', self.bootstrap)


if __name__ == "__main__":
    unittest.main()
