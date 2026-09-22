from __future__ import annotations

import json
import math
import re
import unittest
from pathlib import Path

from build_climax_fork import render_climax_fork_scene
from build_full_piece_bridge_extension import (
    PHASE11_DENSITY_GAP_LENGTH,
    PHASE11_DENSITY_GAP_TIMES,
    build_full_piece_bridge_extension,
)


ROOT = Path(__file__).resolve().parents[2]
MOVEMENT = ROOT / "data/choreography/graceful_opening.movement_demands_v0_1.json"
VISUAL = ROOT / "data/music/graceful_opening.visual_score_v0_1.json"
ACCEPTED_120 = ROOT / "data/geometry/graceful_opening_00_120_topology_v1_1.geometry_plan_v0_1.json"
PLAN_140 = ROOT / "data/geometry/graceful_opening_00_140_bridge.geometry_plan_v0_1.json"
SCENE_140 = ROOT / "scenes/gameplay/generated/graceful_opening_00_140_bridge.tscn"
RUNTIME_140 = ROOT / "scenes/gameplay/generated/graceful_opening_00_140_runtime.tscn"


class Phase113060GameplayDensityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.movement = json.loads(MOVEMENT.read_text(encoding="utf-8"))
        cls.visual = json.loads(VISUAL.read_text(encoding="utf-8"))
        cls.accepted_120 = json.loads(ACCEPTED_120.read_text(encoding="utf-8"))
        cls.plan = json.loads(PLAN_140.read_text(encoding="utf-8"))
        cls.scene = SCENE_140.read_text(encoding="utf-8")
        cls.runtime = RUNTIME_140.read_text(encoding="utf-8")
        _, _, cls.built = build_full_piece_bridge_extension(
            cls.movement,
            cls.visual,
            cls.accepted_120,
        )
        cls.overlay = cls.plan["prototype_overlays"]["phase11_gameplay_density_v1"]

    def test_builder_reproduces_committed_full_piece_plan(self) -> None:
        self.assertEqual(self.built, self.plan)

    def test_builder_reproduces_committed_full_piece_scene(self) -> None:
        self.assertEqual(render_climax_fork_scene(self.built), self.scene)

    def test_density_uses_three_safe_music_aligned_small_gaps(self) -> None:
        self.assertEqual(PHASE11_DENSITY_GAP_TIMES, (43.862, 46.208, 56.889))
        self.assertEqual(PHASE11_DENSITY_GAP_LENGTH, 1.3)
        self.assertEqual(self.overlay["gap_count"], 3)
        self.assertEqual(
            [float(gap["source_time"]) for gap in self.overlay["gaps"]],
            [43.862, 46.208, 56.889],
        )
        self.assertEqual(
            [float(gap["center_x"]) for gap in self.overlay["gaps"]],
            [175.448, 184.832, 227.556],
        )
        self.assertTrue(
            all(
                math.isclose(float(gap["gap_length"]), 1.3, abs_tol=1e-6)
                for gap in self.overlay["gaps"]
            )
        )

    def test_density_gaps_do_not_overlap_runway_ramp_or_fork_collision(self) -> None:
        runways = self.plan["surface_plan"]["runway_intervals"]
        ramps = self.plan["surface_plan"].get("ramps", [])
        forks = [
            event["geometry"]
            for event in self.plan["events"]
            if event["geometry"]["type"] == "ROUTE_FORK"
        ]

        for gap in self.overlay["gaps"]:
            start = float(gap["start_x"])
            end = float(gap["end_x"])
            for interval in runways:
                overlap = min(end, float(interval["end_x"])) - max(
                    start,
                    float(interval["start_x"]),
                )
                self.assertLessEqual(overlap, 1e-6)
            for ramp in ramps:
                overlap = min(end, float(ramp["end_x"])) - max(
                    start,
                    float(ramp["start_x"]),
                )
                self.assertLessEqual(overlap, 1e-6)
            for fork in forks:
                overlap = min(end, float(fork["end_x"])) - max(
                    start,
                    float(fork["start_x"]),
                )
                self.assertLessEqual(overlap, 1e-6)

    def test_scene_has_exact_physical_gap_boundaries(self) -> None:
        expected = {
            30: (174.348, 0.900),
            31: (176.856, 1.516),
            35: (183.685, 0.994),
            36: (186.193, 1.422),
            49: (226.410, 0.992),
            50: (228.918, 1.424),
        }
        for index, (expected_x, expected_length) in expected.items():
            node = re.search(
                rf'\[node name="Runway{index}" type="StaticBody3D" parent="Level"\]\n'
                rf'position = Vector3\(([-0-9.]+),',
                self.scene,
            )
            mesh = re.search(
                rf'\[sub_resource type="BoxMesh" id="BoxMesh_{index}"\]\n'
                rf'material = ExtResource\("2_palace"\)\n'
                rf'size = Vector3\(([-0-9.]+),',
                self.scene,
            )
            self.assertIsNotNone(node)
            self.assertIsNotNone(mesh)
            self.assertTrue(math.isclose(float(node.group(1)), expected_x, abs_tol=1e-4))
            self.assertTrue(
                math.isclose(float(mesh.group(1)), expected_length, abs_tol=1e-4)
            )

    def test_f5_runtime_instantiates_densified_full_piece_scene(self) -> None:
        self.assertIn(
            'path="res://scenes/gameplay/generated/graceful_opening_00_140_bridge.tscn"',
            self.runtime,
        )
        self.assertIn(
            '[node name="GeneratedLevel" parent="."',
            self.runtime,
        )

    def test_accepted_120_source_remains_phase11_free(self) -> None:
        self.assertNotIn(
            "phase11_gameplay_density_v1",
            ACCEPTED_120.read_text(encoding="utf-8"),
        )
        self.assertTrue(self.overlay["accepted_120_source_unchanged"])


if __name__ == "__main__":
    unittest.main()
