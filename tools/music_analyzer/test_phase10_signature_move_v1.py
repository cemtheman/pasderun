from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "scenes" / "characters" / "humanoid_motion_controller.gd"
DIRECTOR = ROOT / "scenes" / "gameplay" / "music_choreography_director.gd"
DEMANDS = ROOT / "data" / "choreography" / "graceful_opening.movement_demands_v0_1.json"
VISUAL_SCORE = ROOT / "data" / "music" / "graceful_opening.visual_score_v0_1.json"


class Phase10SignatureMoveV1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.controller = CONTROLLER.read_text(encoding="utf-8")
        cls.director = DIRECTOR.read_text(encoding="utf-8")
        cls.demands = json.loads(DEMANDS.read_text(encoding="utf-8"))
        cls.visual_score = json.loads(VISUAL_SCORE.read_text(encoding="utf-8"))

    def test_53s_is_strongest_large_travelling_leap_candidate(self) -> None:
        leap_events = []
        for event in self.demands["events"]:
            candidates = event.get("candidate_classes", [])
            if not candidates:
                continue
            primary = candidates[0]
            if primary.get("class") != "LARGE_TRAVELLING_LEAP":
                continue
            leap_events.append(
                (
                    float(event["time"]),
                    float(primary["confidence"]),
                    float(event["musical_context"]["climax_strength"]),
                )
            )

        self.assertEqual(
            [time for time, _, _ in leap_events],
            [32.25, 36.25, 42.5, 53.0],
        )
        strongest = max(leap_events, key=lambda item: item[1])
        self.assertEqual(strongest[0], 53.0)
        self.assertAlmostEqual(strongest[1], 0.8627, places=4)
        self.assertEqual(strongest[2], 1.0)

    def test_visual_score_keeps_53s_as_player_owned_required_jump(self) -> None:
        anchors = [
            anchor
            for anchor in self.visual_score["event_anchors"]
            if abs(float(anchor["time"]) - 53.0) < 1e-9
        ]
        self.assertEqual(len(anchors), 1)
        anchor = anchors[0]
        self.assertEqual(anchor["primary_class"], "LARGE_TRAVELLING_LEAP")
        self.assertTrue(anchor["interaction"]["required"])
        self.assertEqual(anchor["interaction"]["candidate_action"], "JUMP")
        self.assertAlmostEqual(
            float(
                self.visual_score["playability_gate"]["design_limits"][
                    "reaction_lead_seconds"
                ]
            ),
            0.75,
            places=6,
        )

    def test_director_arms_only_named_53s_grand_jete_opportunity(self) -> None:
        for token in (
            'const SIGNATURE_MOVE := &"GRAND_JETE"',
            "const SIGNATURE_MOVE_TIME := 53.0",
            'const SIGNATURE_PRIMARY_CLASS := &"LARGE_TRAVELLING_LEAP"',
            "func _is_signature_preparation_active(playback_time: float)",
            "remaining > _reaction_lead",
            '"set_signature_move_preparation"',
        ):
            self.assertIn(token, self.director)

    def test_director_does_not_execute_gameplay_movement(self) -> None:
        forbidden = (
            "dancer.velocity",
            "dancer.global_position =",
            "dancer.position =",
            "move_and_slide(",
            'call("_jump")',
            "velocity.y =",
        )
        for token in forbidden:
            self.assertNotIn(token, self.director)

    def test_generic_jump_preparation_remains_in_place(self) -> None:
        self.assertIn("func _has_upcoming_required_jump", self.director)
        self.assertIn(
            '"set_music_action_preparation", PREPARATION_ACTION, preparing',
            self.director,
        )
        self.assertIn('const PREPARATION_ACTION := &"JUMP"', self.director)

    def test_signature_activates_only_when_real_jump_state_begins(self) -> None:
        self.assertIn(
            'const SIGNATURE_GRAND_JETE := &"GRAND_JETE"',
            self.controller,
        )
        self.assertIn(
            "func set_signature_move_preparation(move: StringName, active: bool)",
            self.controller,
        )
        state_block = self.controller[
            self.controller.index("func _set_visual_state("):
            self.controller.index("func _apply_visual_overlay(")
        ]
        self.assertIn("if state == STATE_JUMP:", state_block)
        self.assertIn("_activate_prepared_signature_move()", state_block)
        self.assertIn("elif state == STATE_LANDING:", state_block)
        self.assertIn('_active_signature_move = &""', state_block)

    def test_signature_overlay_is_single_humanoid_authority_only(self) -> None:
        self.assertIn(
            "# Phase 10.3 — single humanoid motion authority.",
            self.controller,
        )
        self.assertIn("@onready var _model_root: Node3D = $low_poly_girl", self.controller)
        self.assertIn("func _apply_grand_jete_takeoff_overlay()", self.controller)
        self.assertIn("func _apply_grand_jete_airborne_overlay()", self.controller)
        self.assertNotIn("mannequin", self.controller.lower())

    def test_grand_jete_lead_leg_comes_from_actual_gait_pose(self) -> None:
        self.assertIn("func _current_forward_foot_is_left()", self.controller)
        self.assertIn('_bone_index("left_foot")', self.controller)
        self.assertIn('_bone_index("right_foot")', self.controller)
        self.assertIn(
            "_bone_world_position(left_foot).x",
            self.controller,
        )
        self.assertIn(
            "_bone_world_position(right_foot).x",
            self.controller,
        )

    def test_signature_visual_layer_does_not_take_physics_ownership(self) -> None:
        signature_start = self.controller.index("func _activate_prepared_signature_move()")
        signature_end = self.controller.index("func _apply_landing_overlay()", signature_start)
        signature_source = self.controller[signature_start:signature_end]
        forbidden = (
            "_dancer.velocity =",
            "_dancer.global_position =",
            "_dancer.position =",
            "move_and_slide(",
            'call("_jump")',
        )
        for token in forbidden:
            self.assertNotIn(token, signature_source)


if __name__ == "__main__":
    unittest.main()
