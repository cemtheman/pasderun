import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from second_elbow_line import solve_second_elbow_line  # noqa: E402
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


if __name__ == "__main__":
    unittest.main()
