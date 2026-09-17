from __future__ import annotations

import hashlib
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FLOW = ROOT / "scenes/gameplay/flow_tracker.gd"
MUSICALITY = ROOT / "scenes/gameplay/musicality.gd"
RUNTIME = ROOT / "scenes/gameplay/generated/graceful_opening_00_30_runtime.tscn"
DANCER = ROOT / "scenes/gameplay/dancer.gd"
TIMELINE = ROOT / "scenes/gameplay/music_timeline.gd"
PLAN = ROOT / "data/geometry/graceful_opening.geometry_plan_v0_1.json"
GENERATED = ROOT / "scenes/gameplay/generated/graceful_opening_00_30.tscn"
COMPILER = ROOT / "tools/music_analyzer/compile_geometry.py"

TRUSTED = {
    DANCER: "6068ec94ba4d99fa75180226f2d8cdf0a8172c868b9a4851c7214e1ce0b62748",
    TIMELINE: "605e9605c5a53ec84b862d4ce0b3893802fdfeb36f20dc09b3c67e3a5a183f68",
    PLAN: "6cc084749cc558659016cb5834da0fab8447c155918c16565a35666439ee1fd4",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def constant(source: str, name: str) -> float:
    match = re.search(rf"const {name} := ([0-9.]+)", source)
    if not match:
        raise AssertionError(f"missing numeric constant {name}")
    return float(match.group(1))


class FlowTrackerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.flow = FLOW.read_text(encoding="utf-8")
        cls.musicality = MUSICALITY.read_text(encoding="utf-8")
        cls.runtime = RUNTIME.read_text(encoding="utf-8")

    def test_runtime_wires_isolated_flow_tracker_and_debug_only(self) -> None:
        self.assertIn('path="res://scenes/gameplay/flow_tracker.gd"', self.runtime)
        self.assertIn('name="FlowTracker" type="Node" parent="."', self.runtime)
        self.assertIn('name="FlowDebug" type="Label"', self.runtime)
        self.assertNotIn("score", self.flow.lower())
        self.assertNotIn("currency", self.flow.lower())
        self.assertIsNone(re.search(r"\bxp\b", self.flow.lower()))

    def test_flow_is_clamped_and_states_are_qualitative(self) -> None:
        self.assertIn("flow_value = clampf(value, 0.0, 1.0)", self.flow)
        for state in ("EMPTY", "BUILDING", "FLOWING", "STRONG_FLOW"):
            self.assertIn(state, self.flow)

    def test_accent_contributions_and_nonzeroing_miss(self) -> None:
        perfect = float(re.search(r'&"PERFECT": ([0-9.]+)', self.flow).group(1))
        good = float(re.search(r'&"GOOD": ([0-9.]+)', self.flow).group(1))
        self.assertGreater(perfect, good)
        self.assertGreater(good, 0.0)
        retained = constant(self.flow, "MISS_RETAINED_FRACTION")
        self.assertEqual(retained, 0.60)
        self.assertIn("previous * MISS_RETAINED_FRACTION", self.flow)

    def test_small_timing_errors_reduce_flow_and_break_continuity(self) -> None:
        contributions = re.search(r"const CONTRIBUTIONS := \{(.*?)\n\}", self.flow, re.DOTALL).group(1)
        reductions = re.search(r"const REDUCTIONS := \{(.*?)\n\}", self.flow, re.DOTALL).group(1)
        self.assertNotIn('&"EARLY"', contributions)
        self.assertNotIn('&"LATE"', contributions)
        self.assertIn('&"EARLY": 0.03', reductions)
        self.assertIn('&"LATE": 0.03', reductions)
        self.assertIn("_continuity_links = 0", self.flow)

    def test_musicality_emits_its_actual_classification(self) -> None:
        self.assertIn("signal accent_evaluated", self.musicality)
        self.assertIn("accent_evaluated.emit(classification, delta", self.musicality)
        self.assertEqual(self.musicality.count("const ACCENT_MARKERS"), 1)
        self.assertIn("const ACCENT_MARKERS: Array[float] = [18.0, 22.0, 26.0]", self.musicality)

    def test_only_validated_outcomes_build_flow(self) -> None:
        self.assertIn("dancer.is_on_floor()", self.flow)
        self.assertIn('event["airborne"]', self.flow)
        self.assertIn("MEANINGFUL_HOLD_SECONDS", self.flow)
        self.assertIn("TECHNICAL ROUTE COMPLETE", self.flow)
        self.assertIn("SAFE ROUTE COMPLETE", self.flow)
        self.assertNotIn("tap_detected", self.flow)
        self.assertNotIn("Input.", self.flow)

    def test_failed_semantic_outcomes_reduce_flow(self) -> None:
        self.assertIn('REDUCTIONS[&"POOR_LANDING"]', self.flow)
        self.assertIn('REDUCTIONS[&"PHRASE_BREAK"]', self.flow)
        self.assertIn("BALANCE PHRASE BREAK", self.flow)
        self.assertIn("ROUTE PHRASE BREAK", self.flow)
        self.assertIn("func _apply_reduction", self.flow)

    def test_continuity_rewards_sequences_not_input_spam(self) -> None:
        bonus = constant(self.flow, "CONTINUITY_BONUS_PER_LINK")
        self.assertGreater(bonus, 0.0)
        self.assertIn("playback_time - _last_success_time <= CONTINUITY_WINDOW_SECONDS", self.flow)
        self.assertIn("base_amount + CONTINUITY_BONUS_PER_LINK * _continuity_links", self.flow)
        jump = float(re.search(r'&"JUMP": ([0-9.]+)', self.flow).group(1))
        isolated_pair = jump + jump
        connected_pair = jump + (jump + bonus)
        self.assertGreater(connected_pair, isolated_pair)

    def test_one_miss_reduces_but_preserves_established_flow(self) -> None:
        retained = constant(self.flow, "MISS_RETAINED_FRACTION")
        established_flow = 0.60
        after_miss = established_flow * retained
        self.assertAlmostEqual(after_miss, 0.36)
        self.assertGreater(after_miss, 0.0)
        self.assertLess(after_miss, established_flow)

    def test_miss_reduction_is_applied_synchronously_in_signal_callback(self) -> None:
        callback = re.search(
            r"func _on_accent_evaluated\(.*?(?=\n\nfunc )",
            self.flow,
            re.DOTALL,
        )
        self.assertIsNotNone(callback)
        source = callback.group(0)
        self.assertIn('if classification == &"MISS":', source)
        self.assertIn("last_miss_after = clampf(previous * MISS_RETAINED_FRACTION, 0.0, 1.0)", source)
        self.assertIn("_set_flow(last_miss_after, reason)", source)
        self.assertNotIn("call_deferred", source)
        self.assertNotIn("await", source)

    def test_miss_result_cannot_be_replaced_before_hud_draw(self) -> None:
        callback = re.search(
            r"func _on_accent_evaluated\(.*?(?=\n\nfunc )",
            self.flow,
            re.DOTALL,
        ).group(0)
        physics = re.search(
            r"func _physics_process\(.*?(?=\n\nfunc )",
            self.flow,
            re.DOTALL,
        ).group(0)
        self.assertIn("Engine.get_process_frames() + 1", callback)
        self.assertIn("Engine.get_process_frames() <= _miss_visible_through_process_frame", physics)
        self.assertLess(
            physics.index("SERIOUS INTERRUPTION: FALL"),
            physics.index("_miss_visible_through_process_frame"),
        )

    def test_all_other_flow_tuning_values_remain_locked(self) -> None:
        expected_contributions = {
            "JUMP": 0.14,
            "BALANCE": 0.14,
            "SAFE_ROUTE": 0.08,
            "TECHNICAL_ROUTE": 0.14,
            "PERFECT": 0.16,
            "GOOD": 0.11,
        }
        for name, expected in expected_contributions.items():
            actual = float(re.search(rf'&"{name}": ([0-9.]+)', self.flow).group(1))
            self.assertEqual(actual, expected)
        expected_reductions = {
            "EARLY": 0.03,
            "LATE": 0.03,
            "POOR_LANDING": 0.08,
            "PHRASE_BREAK": 0.06,
        }
        reductions = re.search(r"const REDUCTIONS := \{(.*?)\n\}", self.flow, re.DOTALL).group(1)
        for name, expected in expected_reductions.items():
            actual = float(re.search(rf'&"{name}": ([0-9.]+)', reductions).group(1))
            self.assertEqual(actual, expected)
        self.assertEqual(constant(self.flow, "DECAY_GRACE_SECONDS"), 6.0)
        self.assertEqual(constant(self.flow, "DECAY_PER_SECOND"), 0.01)
        for state, expected in (("BUILDING", 0.05), ("FLOWING", 0.45), ("STRONG_FLOW", 0.75)):
            actual = float(re.search(rf'&"{state}": ([0-9.]+)', self.flow).group(1))
            self.assertEqual(actual, expected)

    def test_safe_and_technical_routes_are_both_valid_with_technical_upside(self) -> None:
        safe = float(re.search(r'&"SAFE_ROUTE": ([0-9.]+)', self.flow).group(1))
        technical = float(re.search(r'&"TECHNICAL_ROUTE": ([0-9.]+)', self.flow).group(1))
        self.assertGreater(safe, 0.0)
        self.assertGreater(technical, safe)
        self.assertIn('branch["routes"]["technical"]["segments"]', self.flow)
        self.assertIn('branch["routes"]["safe"]["elevation"]', self.flow)

    def test_recovery_decay_is_delayed_and_gentle(self) -> None:
        grace = constant(self.flow, "DECAY_GRACE_SECONDS")
        rate = constant(self.flow, "DECAY_PER_SECOND")
        self.assertGreaterEqual(grace, 5.0)
        self.assertLessEqual(rate, 0.02)

    def test_fall_and_restart_reset_deterministically(self) -> None:
        self.assertIn('_reset_flow("SERIOUS INTERRUPTION: FALL")', self.flow)
        self.assertIn('_reset_flow("RESTART / SEEK")', self.flow)
        self.assertIn("_reset_opportunities()", self.flow)

    def test_opportunities_come_from_geometry_plan_not_hardcoded_times(self) -> None:
        self.assertIn("geometry_plan_path", self.flow)
        self.assertIn('plan["events"]', self.flow)
        for timestamp in ("7.25", "11.5", "22.25"):
            self.assertNotIn(timestamp, self.flow)

    def test_trusted_movement_music_geometry_and_compiler_are_unchanged(self) -> None:
        for path, expected in TRUSTED.items():
            self.assertEqual(digest(path), expected, path)
        self.assertNotIn("FlowTracker", COMPILER.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
