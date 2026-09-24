import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from hand_clearance_candidate import shifted_solution  # noqa: E402
from port_de_bras_path import sample_port_de_bras  # noqa: E402
from second_elbow_line import solve_second_forward_line  # noqa: E402
from validate import ContractError  # noqa: E402


FRAME = {"left": [1, 0, 0], "up": [0, 1, 0], "front": [0, 0, 1]}
# Representative normalized landmark measurements from the existing Phase 10
# source bridge. Values are fixture evidence, not new authored pose targets.
LEFT = {
    "bras_bas": [[.10040356, .40294418, -.01856421],
                 [.13385134, .23585480, .01384403],
                 [.01328369, .11576959, .06243375],
                 [0, .10731634, .07088701]],
    "en_avant": [[.10040356, .40294418, -.01856421],
                 [.12983220, .37972799, .15079598],
                 [.00502679, .34730432, .27199950],
                 [0, .34550904, .28905469]],
    "second": [[.10040356, .40294418, -.01856421],
               [.27139202, .41701889, .00698492],
               [.42546852, .32997042, .00797171],
               [.44188356, .32497453, .01296759]],
}


def source(pose):
    left = dict(zip(("shoulder", "elbow", "wrist", "hand"), LEFT[pose]))
    right = {name: [-point[0], point[1], point[2]] for name, point in left.items()}
    return {"pose_id": pose, "arms": {"left": left, "right": right}}


class PortDeBrasPathTests(unittest.TestCase):
    def test_all_samples_keep_lengths_bend_side_and_exact_waypoints(self):
        poses = {
            "bras_bas": shifted_solution(source("bras_bas"), FRAME, .12825477 / 1.44988),
            "en_avant": shifted_solution(source("en_avant"), FRAME,
                                          .09751075 / 1.44988, "body_outward"),
            "second": solve_second_forward_line(source("second"), FRAME)[0],
        }
        samples = sample_port_de_bras(poses, FRAME)
        self.assertEqual([sample["frame"] for sample in samples], list(range(1, 50)))
        for sample, pose in ((samples[0], "bras_bas"), (samples[24], "en_avant"),
                             (samples[48], "second")):
            self.assertEqual(sample["arms"], poses[pose]["arms"])
        for sample in samples:
            for side in ("left", "right"):
                arm = sample["arms"][side]
                self.assertGreater(sample["inward_flexion"][side]["signed_inward_alignment"], 0)
                for a, b in (("shoulder", "elbow"), ("elbow", "wrist"),
                             ("wrist", "hand")):
                    self.assertAlmostEqual(math.dist(arm[a], arm[b]),
                                           math.dist(poses["bras_bas"]["arms"][side][a],
                                                     poses["bras_bas"]["arms"][side][b]), places=5)

    def test_changed_shoulder_is_rejected(self):
        start = source("bras_bas")
        end = source("bras_bas")
        end["arms"]["left"]["shoulder"] = [0, 0, 0]
        with self.assertRaisesRegex(ContractError, "shoulder changes"):
            sample_port_de_bras({"bras_bas": start, "en_avant": end,
                                 "second": source("bras_bas")}, FRAME)


if __name__ == "__main__":
    unittest.main()
