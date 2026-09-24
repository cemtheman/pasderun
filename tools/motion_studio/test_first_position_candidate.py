import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from first_position_candidate import guide_first_position  # noqa: E402
from hand_clearance_candidate import shifted_solution  # noqa: E402
from static_pose import dot  # noqa: E402
from test_port_de_bras_path import FRAME, source  # noqa: E402
from validate import ContractError  # noqa: E402


class FirstPositionCandidateTests(unittest.TestCase):
    def test_midpoint_wrist_is_lower_and_preserves_measured_segments(self):
        low = shifted_solution(source("bras_bas"), FRAME, .12825477 / 1.44988)
        high = shifted_solution(source("en_avant"), FRAME,
                                .09751075 / 1.44988, "body_outward")
        first = guide_first_position(low, high, FRAME)
        for side in ("left", "right"):
            a, b, c = low["arms"][side], high["arms"][side], first["arms"][side]
            self.assertAlmostEqual(dot(c["wrist"], FRAME["up"]),
                                   (dot(a["wrist"], FRAME["up"]) +
                                    dot(b["wrist"], FRAME["up"])) / 2)
            self.assertAlmostEqual(dot(c["wrist"], FRAME["front"]),
                                   (dot(a["wrist"], FRAME["front"]) +
                                    dot(b["wrist"], FRAME["front"])) / 2)
            self.assertAlmostEqual(dot(c["wrist"], FRAME["left"]),
                                   dot(b["wrist"], FRAME["left"]))
            for start, end in (("shoulder", "elbow"), ("elbow", "wrist"),
                               ("wrist", "hand")):
                self.assertAlmostEqual(math.dist(b[start], b[end]),
                                       math.dist(c[start], c[end]), places=6)

    def test_unordered_sources_rejected(self):
        with self.assertRaisesRegex(ContractError, "wrong source poses"):
            guide_first_position(source("en_avant"), source("bras_bas"), FRAME)


if __name__ == "__main__":
    unittest.main()
