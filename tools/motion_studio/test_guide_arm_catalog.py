import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from first_position_candidate import guide_first_position  # noqa: E402
from guide_arm_catalog import (combine_arm_positions, crown_position,
                               route_arm_positions, sample_arm_transition)  # noqa: E402
from hand_clearance_candidate import shifted_solution  # noqa: E402
from second_elbow_line import solve_second_forward_line  # noqa: E402
from test_port_de_bras_path import FRAME, source  # noqa: E402


class GuideArmCatalogTests(unittest.TestCase):
    def setUp(self):
        low = shifted_solution(source("bras_bas"), FRAME, .12825477 / 1.44988)
        high = shifted_solution(source("en_avant"), FRAME,
                                .09751075 / 1.44988, "body_outward")
        first = guide_first_position(low, high, FRAME, navel_region_height=.178)
        second = solve_second_forward_line(source("second"), FRAME)[0]
        crown = crown_position(second, FRAME, .64)
        self.poses = {"bra_bas": low, "first": first, "second": second,
                      "fifth": crown,
                      "third_left_first": combine_arm_positions("third_left_first", first, second),
                      "third_right_first": combine_arm_positions("third_right_first", second, first),
                      "fourth_left_crown": combine_arm_positions("fourth_left_crown", crown, second),
                      "fourth_right_crown": combine_arm_positions("fourth_right_crown", second, crown)}

    def test_crown_above_shoulders_and_segments_preserved(self):
        for side in ("left", "right"):
            crown = self.poses["fifth"]["arms"][side]
            second = self.poses["second"]["arms"][side]
            self.assertGreater(crown["wrist"][1], crown["shoulder"][1])
            reach = math.dist(crown["shoulder"], crown["elbow"]) + math.dist(crown["elbow"], crown["wrist"])
            self.assertGreater(crown["wrist"][1], .64 + .12 * reach)
            for a, b in (("shoulder", "elbow"), ("elbow", "wrist"), ("wrist", "hand")):
                self.assertAlmostEqual(math.dist(crown[a], crown[b]),
                                       math.dist(second[a], second[b]), places=6)

    def test_all_catalog_nodes_connected_by_safe_arm_edges(self):
        pairs = (("bra_bas", "first"), ("first", "second"),
                 ("first", "fifth"),
                 ("first", "third_left_first"), ("first", "third_right_first"),
                 ("third_left_first", "fourth_left_crown"),
                 ("third_right_first", "fourth_right_crown"))
        for start, end in pairs:
            with self.subTest(start=start, end=end):
                frames = sample_arm_transition(self.poses[start], self.poses[end], FRAME)
                self.assertEqual(frames[0]["arms"], self.poses[start]["arms"])
                self.assertEqual(frames[-1]["arms"], self.poses[end]["arms"])
                for sample in frames:
                    for side, arm in sample["arms"].items():
                        self.assertGreater(sample["inward_flexion"][side]["signed_inward_alignment"], 0)
                        baseline = self.poses[start]["arms"][side]
                        for a, b in (("shoulder", "elbow"), ("elbow", "wrist"), ("wrist", "hand")):
                            self.assertAlmostEqual(math.dist(arm[a], arm[b]),
                                                   math.dist(baseline[a], baseline[b]), places=5)
        graph = dict.fromkeys(pairs, [])
        for start in self.poses:
            for end in self.poses:
                route = route_arm_positions(start, end, graph)
                self.assertEqual((route[0], route[-1]), (start, end))
                for a, b in zip(route, route[1:]):
                    self.assertTrue((a, b) in graph or (b, a) in graph)


if __name__ == "__main__":
    unittest.main()
