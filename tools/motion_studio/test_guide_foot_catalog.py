import math
import pathlib
import sys
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from guide_foot_catalog import (FOOT_POSITIONS, guide_foot_position,
                                sample_foot_transition)  # noqa: E402
from test_port_de_bras_path import FRAME  # noqa: E402


def fixture():
    bones, soles = {}, {}
    for side, sign in (("left", 1), ("right", -1)):
        x = sign * .15
        for name, head in (("thigh", [x, .84, 0]),
                           ("shin", [x, .48, .04]),
                           ("foot", [x, .11, .02]),
                           ("toes", [x, .09, .17])):
            bones[f"{side}_{name}"] = {"head_local": head, "rig_bone": f"{side}_{name}"}
        soles[side] = {"points": [
            {"position_armature_local": [x + dx, 0, z]}
            for dx in (-.03, .03) for z in (-.09, .08)]}
    return {"anatomical_frame": FRAME, "canonical_bones": bones}, soles


class GuideFootCatalogTests(unittest.TestCase):
    def test_targets_keep_leg_lengths_and_heel_height(self):
        calibration, soles = fixture()
        for name in FOOT_POSITIONS:
            with self.subTest(name=name):
                pose = guide_foot_position(calibration, soles, name)
                self.assertEqual(set(pose["legs"]), {"left", "right"})
                for side, leg in pose["legs"].items():
                    self.assertAlmostEqual(leg["heel"][1], 0)
                    original = calibration["canonical_bones"]
                    self.assertAlmostEqual(math.dist(leg["hip"], leg["knee"]),
                        math.dist(original[f"{side}_thigh"]["head_local"],
                                  original[f"{side}_shin"]["head_local"]), places=6)
                    self.assertAlmostEqual(math.dist(leg["knee"], leg["ankle"]),
                        math.dist(original[f"{side}_shin"]["head_local"],
                                  original[f"{side}_foot"]["head_local"]), places=6)

    def test_degenerate_sole_is_rejected(self):
        calibration, soles = fixture()
        soles["left"]["points"] = soles["left"]["points"][:2]
        with self.assertRaisesRegex(ValueError, "insufficient"):
            guide_foot_position(calibration, soles, "first")

    def test_first_position_connects_to_catalog_targets(self):
        calibration, soles = fixture()
        first = guide_foot_position(calibration, soles, "first")
        for name in FOOT_POSITIONS[1:]:
            with self.subTest(name=name):
                end = guide_foot_position(calibration, soles, name)
                samples = sample_foot_transition(first, end, FRAME)
                self.assertEqual(samples[0]["legs"], first["legs"])
                self.assertEqual(samples[-1]["legs"], end["legs"])
                for sample in samples:
                    for side, leg in sample["legs"].items():
                        self.assertAlmostEqual(math.dist(leg["hip"], leg["knee"]),
                                               math.dist(first["legs"][side]["hip"],
                                                         first["legs"][side]["knee"]), places=5)


if __name__ == "__main__":
    unittest.main()
