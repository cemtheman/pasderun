from __future__ import annotations

import json
import unittest
from pathlib import Path

from build_full_piece_bridge_extension import (
    BASELINE_END_X,
    build_full_piece_bridge_extension,
)


ROOT = Path(__file__).resolve().parents[2]
DEMANDS = json.loads(
    (ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json").read_text(encoding="utf-8")
)
VISUAL = json.loads(
    (ROOT / "data/music/graceful_opening.visual_score_v0_1.json").read_text(encoding="utf-8")
)
BASELINE = json.loads(
    (ROOT / "data/geometry/graceful_opening_00_120_topology_v1_1.geometry_plan_v0_1.json").read_text(encoding="utf-8")
)


class Phase9BridgeTopologyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.base, cls.spatial, cls.plan = build_full_piece_bridge_extension(
            DEMANDS,
            VISUAL,
            BASELINE,
        )
        cls.bridge = cls.plan["prototype_overlays"]["architectural_spans_v1"][0]

    def test_full_piece_uses_exact_visual_score_duration(self) -> None:
        self.assertEqual(float(self.plan["compiled_time_range"]["end"]), 140.016)
        self.assertAlmostEqual(
            float(self.plan["playable_world_extent"]["end_x"]),
            140.016 * 4.0 + 8.0,
            places=3,
        )

    def test_accepted_zero_to_120_event_contract_is_frozen(self) -> None:
        expected = [
            event for event in BASELINE["events"]
            if float(event["source_time"]) <= 120.0
        ]
        actual = [
            event for event in self.plan["events"]
            if float(event["source_time"]) <= 120.0
        ]
        self.assertEqual(actual, expected)

    def test_accepted_zero_to_120_runway_prefix_and_ramps_are_frozen(self) -> None:
        expected = []
        for runway in BASELINE["surface_plan"]["runway_intervals"]:
            left = float(runway["start_x"])
            right = min(float(runway["end_x"]), BASELINE_END_X)
            if left >= BASELINE_END_X or right <= left:
                continue
            expected.append({
                "start_x": round(left, 4),
                "end_x": round(right, 4),
                "surface_y": round(float(runway["surface_y"]), 4),
            })
        actual = [
            runway for runway in self.plan["surface_plan"]["runway_intervals"]
            if float(runway["end_x"]) <= BASELINE_END_X + 1e-6
        ]
        self.assertEqual(actual, expected)
        self.assertEqual(
            self.plan["surface_plan"].get("ramps", []),
            BASELINE["surface_plan"].get("ramps", []),
        )

    def test_final_legato_phrase_becomes_shared_route_bridge(self) -> None:
        self.assertEqual(self.bridge["topology"], "BRIDGE")
        self.assertTrue(self.bridge["shared_route"])
        self.assertEqual(self.bridge["start_time"], 137.753)
        self.assertEqual(self.bridge["end_time"], 140.016)
        self.assertEqual(self.bridge["source_roles"], ["SUSTAIN", "SUSTAIN"])
        self.assertEqual(self.bridge["source_articulation"], "LEGATO")
        self.assertFalse(self.bridge["new_required_actions"])

    def test_bridge_span_is_one_flat_collision_runway(self) -> None:
        start_x = float(self.bridge["start_x"])
        end_x = float(self.bridge["end_x"])
        exact = [
            runway for runway in self.plan["surface_plan"]["runway_intervals"]
            if abs(float(runway["start_x"]) - start_x) <= 1e-4
            and abs(float(runway["end_x"]) - end_x) <= 1e-4
        ]
        self.assertEqual(len(exact), 1)
        self.assertEqual(
            float(exact[0]["surface_y"]),
            float(self.bridge["surface_y"]),
        )

    def test_extension_required_actions_remain_visual_score_actions_only(self) -> None:
        anchors = [
            (float(anchor["time"]), anchor["interaction"]["candidate_action"])
            for anchor in VISUAL["event_anchors"]
            if 120.0 <= float(anchor["time"]) < 140.016
            and bool(anchor["interaction"]["required"])
        ]
        self.assertEqual(
            anchors,
            [
                (120.628, "TAP"),
                (122.5, "TAP"),
                (128.0, "JUMP"),
                (135.5, "TAP"),
            ],
        )

    def test_builder_is_deterministic(self) -> None:
        base, spatial, plan = build_full_piece_bridge_extension(
            DEMANDS,
            VISUAL,
            BASELINE,
        )
        self.assertEqual(self.base, base)
        self.assertEqual(self.spatial, spatial)
        self.assertEqual(self.plan, plan)


if __name__ == "__main__":
    unittest.main()
