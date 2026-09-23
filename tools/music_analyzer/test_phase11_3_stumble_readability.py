from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VISUAL = (
    ROOT / "scenes/characters/humanoid_motion_controller.gd"
).read_text(encoding="utf-8")
DANCER = (ROOT / "scenes/gameplay/dancer.gd").read_text(encoding="utf-8")


class Phase113StumbleReadabilityTests(unittest.TestCase):
    def test_stumble_preempts_generic_landing_overlay(self) -> None:
        resolver = VISUAL.index("func _resolve_visual_state(delta: float) -> StringName:")
        stumble = VISUAL.index("if locomotion == STATE_STUMBLE:", resolver)
        recovery = VISUAL.index("if locomotion == STATE_RECOVERY:", stumble)
        landing = VISUAL.index("if _landing_time > 0.0:", recovery)
        self.assertLess(stumble, landing)
        self.assertLess(recovery, landing)

    def test_pending_landing_is_cleared_for_stumble_chain(self) -> None:
        self.assertIn(
            "if locomotion == STATE_STUMBLE:\n"
            "\t\t_landing_time = 0.0\n"
            "\t\treturn STATE_STUMBLE",
            VISUAL,
        )
        self.assertIn(
            "if locomotion == STATE_RECOVERY:\n"
            "\t\t_landing_time = 0.0\n"
            "\t\treturn STATE_RECOVERY",
            VISUAL,
        )

    def test_normal_landing_visual_is_preserved(self) -> None:
        self.assertIn("const LANDING_VISUAL_TIME := 0.24", VISUAL)
        self.assertIn("return STATE_LANDING", VISUAL)
        self.assertIn("func _apply_landing_overlay() -> void:", VISUAL)

    def test_gameplay_stumble_timing_and_speed_are_unchanged(self) -> None:
        self.assertIn("const STUMBLE_DURATION := 0.36", DANCER)
        self.assertIn("const RECOVERY_DURATION := 0.72", DANCER)
        self.assertIn("const STUMBLE_SPEED_MULTIPLIER := 0.68", DANCER)
        self.assertIn("const RECOVERY_SPEED_MULTIPLIER := 1.05", DANCER)

    def test_reference_guided_catch_step_is_bounded(self) -> None:
        self.assertIn("const RECOVERY_CATCH_FORWARD_START := 0.40", VISUAL)
        self.assertIn("const RECOVERY_CATCH_FORWARD_ACCEPT := 0.26", VISUAL)
        self.assertIn("const RECOVERY_TRAIL_BACK := 0.30", VISUAL)
        self.assertNotIn("lerpf(0.64, 0.30", VISUAL)
        self.assertIn("0.18 * leg_length", VISUAL)

    def test_trip_leg_authority_continues_into_recovery(self) -> None:
        self.assertIn("var free_left := not _trip_uses_left_foot", VISUAL)
        self.assertIn("var trail_hip := _bone_index(", VISUAL)
        self.assertIn("var trail_foot_target := Vector3(", VISUAL)
        self.assertIn(
            "pelvis_position.x - RECOVERY_TRAIL_BACK * leg_length",
            VISUAL,
        )

    def test_torso_and_arms_keep_forward_rescue_language(self) -> None:
        self.assertIn("const STUMBLE_TORSO_PITCH := deg_to_rad(32.0)", VISUAL)
        self.assertIn("var torso_release := smoothstep(0.42, 0.94, t)", VISUAL)
        self.assertIn("0.58 if same_side_as_catch else 0.70", VISUAL)
        self.assertIn("0.48 if same_side_as_trip else 0.58", VISUAL)

    def test_existing_stumble_state_authority_remains_intact(self) -> None:
        self.assertIn("func _apply_stumble_overlay() -> void:", VISUAL)
        self.assertIn("func _apply_recovery_overlay() -> void:", VISUAL)
        self.assertIn("_capture_trip_side_from_current_gait()", VISUAL)


if __name__ == "__main__":
    unittest.main()
