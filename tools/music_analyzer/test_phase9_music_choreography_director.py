from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DIRECTOR = ROOT / "scenes/gameplay/music_choreography_director.gd"
VISUAL = ROOT / "scenes/gameplay/dancer_visual.gd"
VISUAL_V5 = ROOT / "scenes/gameplay/dancer_visual_motion_v5.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_60_runtime.tscn"


class Phase9MusicChoreographyDirectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.director = DIRECTOR.read_text(encoding="utf-8")
        cls.visual = VISUAL.read_text(encoding="utf-8")
        cls.visual_v5 = VISUAL_V5.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_phase9_body_expression_starts_after_accepted_30s_baseline(self) -> None:
        self.assertIn("const ACTIVATION_TIME := 30.0", self.director)
        self.assertIn('set_music_expression_enabled", false', self.director)
        self.assertIn('set_music_expression_enabled", true', self.director)

    def test_director_consumes_visual_score_and_playability_reaction_lead(self) -> None:
        self.assertIn("graceful_opening.visual_score_v0_1.json", self.director)
        self.assertIn('"windows"', self.director)
        self.assertIn('"event_anchors"', self.director)
        self.assertIn('"reaction_lead_seconds"', self.director)

    def test_director_never_executes_gameplay_movement(self) -> None:
        forbidden = (
            "dancer.velocity",
            "dancer.global_position =",
            "dancer.position =",
            "move_and_slide(",
            'call("_jump")',
            "in_low_transition =",
        )
        for token in forbidden:
            self.assertNotIn(token, self.director)

    def test_required_jump_is_prepared_but_remains_player_owned(self) -> None:
        self.assertIn('const PREPARATION_ACTION := &"JUMP"', self.director)
        self.assertIn("_has_upcoming_required_jump", self.director)
        self.assertIn("set_music_action_preparation", self.director)
        self.assertNotIn("jump_velocity", self.director)

    def test_successful_tap_becomes_visible_body_accent(self) -> None:
        self.assertIn('musicality.connect(&"accent_evaluated"', self.director)
        self.assertIn('classification == &"MISS"', self.director)
        self.assertIn('trigger_music_accent', self.director)
        self.assertIn("STATE_MUSIC_ACCENT", self.visual)

    def test_music_phrase_states_exist_without_replacing_physics_priority(self) -> None:
        for state in (
            "MUSIC_FLOW",
            "MUSIC_BUILD",
            "MUSIC_RELEASE",
            "MUSIC_PULSE",
            "MUSIC_CLIMAX",
            "MUSIC_PREP",
            "MUSIC_ACCENT",
        ):
            self.assertIn(f'&"{state}"', self.visual)

        resolver = re.search(r"func _resolve_visual_state\(.*?(?=\n\nfunc |\Z)", self.visual, re.DOTALL)
        self.assertIsNotNone(resolver)
        source = resolver.group(0)
        self.assertLess(source.index("in_low_transition"), source.index("_music_expression_enabled"))
        self.assertLess(source.index("in_balance_zone"), source.index("_music_expression_enabled"))
        self.assertLess(source.index("not grounded"), source.index("_music_expression_enabled"))
        self.assertLess(source.index("STATE_LANDING"), source.index("_music_expression_enabled"))

    def test_v5_has_distinct_phrase_motion_not_aliases(self) -> None:
        for function in (
            "_music_build_animation",
            "_music_release_animation",
            "_music_pulse_animation",
            "_music_climax_animation",
            "_music_prep_animation",
            "_music_accent_animation",
        ):
            self.assertIn(f"func {function}()", self.visual_v5)
        self.assertIn("_front_contact_pose()", self.visual_v5)
        self.assertIn("_back_contact_pose()", self.visual_v5)
        self.assertIn("_music_pose", self.visual_v5)

    def test_runtime_wires_director_and_debug_hud(self) -> None:
        self.assertIn("music_choreography_director.gd", self.runtime)
        self.assertIn('name="MusicChoreographyDirector"', self.runtime)
        self.assertIn('name="ChoreographyDebug"', self.runtime)
        self.assertIn('text = "CHOREO: BASELINE"', self.runtime)


if __name__ == "__main__":
    unittest.main()
