import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from second_elbow_line import solve_second_elbow_line, solve_second_forward_line  # noqa: E402
from validate import ContractError  # noqa: E402


class SecondElbowLineTests(unittest.TestCase):
    def test_elbow_between_shoulder_and_wrist_and_segments_preserved(self):
        arms = {}
        for side, sign in (("left", 1), ("right", -1)):
            arms[side] = {"shoulder": [sign * .2, 0, 1],
                          "elbow": [sign * .4, .1, 1.05],
                          "wrist": [sign * .6, .1, .8],
                          "hand": [sign * .7, .1, .75]}
        source = {"pose_id": "second", "arms": arms}
        result = solve_second_elbow_line(source, {"up": [0, 0, 1]})
        for side in ("left", "right"):
            old, new = arms[side], result["arms"][side]
            self.assertAlmostEqual(new["elbow"][2], .9)
            self.assertEqual(new["wrist"], old["wrist"])
            self.assertEqual(new["hand"], old["hand"])
            for a, b in (("shoulder", "elbow"), ("elbow", "wrist")):
                self.assertAlmostEqual(math.dist(old[a], old[b]), math.dist(new[a], new[b]))
        self.assertEqual(source["arms"]["left"]["elbow"], [.4, .1, 1.05])

    def test_rejects_invalid_pose_and_ascending_wrist(self):
        arm = {"shoulder": [0, 0, 1], "elbow": [.1, 0, 1], "wrist": [.2, 0, 1.1]}
        with self.assertRaisesRegex(ContractError, "requires second"):
            solve_second_elbow_line({"pose_id": "en_avant", "arms": {"left": arm}}, {"up": [0, 0, 1]})
        with self.assertRaisesRegex(ContractError, "shoulder must be above wrist"):
            solve_second_elbow_line({"pose_id": "second", "arms": {"left": arm}}, {"up": [0, 0, 1]})

    def test_forward_line_repairs_backward_forearm_without_extending_arm(self):
        # Representative accepted second-position joint centers: original elbow
        # sits above the shoulder, while the old fixed wrist is too far back.
        left = {"shoulder": [.10040356, .40294418, -.01856421],
                "elbow": [.27139202, .41701889, .00698492],
                "wrist": [.42546852, .32997042, .00797171],
                "hand": [.44188356, .32497453, .01296759]}
        right = {key: [-point[0], point[1], point[2]] for key, point in left.items()}
        source = {"pose_id": "second", "arms": {"left": left, "right": right}}
        frame = {"up": [0, 1, 0], "front": [0, 0, 1], "left": [1, 0, 0]}
        candidate, diagnostics = solve_second_forward_line(source, frame)
        for side in ("left", "right"):
            old, new = source["arms"][side], candidate["arms"][side]
            self.assertGreater(old["elbow"][1], old["shoulder"][1])
            self.assertGreater(new["shoulder"][1], new["elbow"][1])
            self.assertGreater(new["elbow"][1], new["wrist"][1])
            self.assertLess(new["shoulder"][2], new["elbow"][2])
            self.assertLess(new["elbow"][2], new["wrist"][2])
            self.assertLess(diagnostics[side]["side_turn_deg"], 20)
            self.assertLess(diagnostics[side]["elbow_interior_deg"], 170)
            self.assertGreater(diagnostics[side]["inward_flexion"]["signed_inward_alignment"], 0)
            for a, b in (("shoulder", "elbow"), ("elbow", "wrist"), ("wrist", "hand")):
                self.assertAlmostEqual(math.dist(old[a], old[b]), math.dist(new[a], new[b]))
            self.assertEqual(new["wrist"][1], old["wrist"][1])
        self.assertEqual(left["wrist"], [.42546852, .32997042, .00797171])


if __name__ == "__main__":
    unittest.main()
