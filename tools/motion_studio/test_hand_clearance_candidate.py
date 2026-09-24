import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hand_clearance_candidate import shifted_solution  # noqa: E402
from validate import ContractError  # noqa: E402


class HandClearanceCandidateTests(unittest.TestCase):
    def test_moves_wrists_outward_and_preserves_link_and_hand_lengths(self):
        left = {"shoulder": [.2, 0, 0], "elbow": [.4, -.1, 0],
                "wrist": [.1, -.3, 0], "hand": [.05, -.32, 0],
                "bone_names": ["a", "b", "c"], "arm_reach": .6}
        right = {**left, **{joint: [-v[0], v[1], v[2]] for joint, v in left.items()
                          if joint in ("shoulder", "elbow", "wrist", "hand")}}
        source = {"pose_id": "bras_bas", "arms": {"left": left, "right": right}}
        result = shifted_solution(source, {"left": [1, 0, 0]}, .04)
        self.assertAlmostEqual(result["arms"]["left"]["wrist"][0], .14)
        self.assertAlmostEqual(result["arms"]["right"]["wrist"][0], -.14)
        for side in ("left", "right"):
            arm = result["arms"][side]
            original = source["arms"][side]
            for a, b in (("shoulder", "elbow"), ("elbow", "wrist"), ("wrist", "hand")):
                self.assertAlmostEqual(math.dist(arm[a], arm[b]), math.dist(original[a], original[b]))
        self.assertEqual(source["arms"]["left"]["wrist"], [.1, -.3, 0])

    def test_rejects_unreachable_shift_and_wrong_pose(self):
        arm = {"shoulder": [0, 0, 0], "elbow": [.1, .2, 0],
               "wrist": [0, .3, 0], "hand": [0, .34, 0]}
        spec = {"pose_id": "en_avant", "arms": {"left": arm}}
        with self.assertRaisesRegex(ContractError, "unreachable"):
            shifted_solution(spec, {"left": [1, 0, 0]}, 5)
        spec["pose_id"] = "second"
        with self.assertRaisesRegex(ContractError, "only inward"):
            shifted_solution(spec, {"left": [1, 0, 0]}, 0)


if __name__ == "__main__":
    unittest.main()
