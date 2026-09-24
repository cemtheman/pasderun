import copy
import sys
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from contact_support import solve_contact_support  # noqa: E402
from validate import ContractError  # noqa: E402


def patch(side, x):
    coords = [(x-0.1, -0.2), (x+0.1, -0.2), (x+0.1, 0.2), (x-0.1, 0.2)]
    return {"id": side, "side": side, "source": {"kind": "measured_mesh", "reference": f"fixture_{side}"},
            "points": [{"position_armature_local": [a, -b, 0.01], "reference": f"v{i}"}
                       for i, (a, b) in enumerate(coords)]}


class ContactSupportTests(unittest.TestCase):
    def setUp(self):
        self.spec = {
            "schema_version": "0.4.0", "pose_id": "fixture", "rig_profile_id": "low_poly_girl_rig_v0",
            "source_glb_sha256": "a" * 64,
            "anatomical_frame": {"left": [1, 0, 0], "up": [0, 0, 1], "front": [0, -1, 0]},
            "ground_height_up": 0, "max_contact_height_spread": 0.001,
            "patches": [patch("left", 0.3), patch("right", -0.3)],
            "active_patch_ids": ["left", "right"],
        }

    def test_two_foot_support_and_vertical_alignment_without_com(self):
        result = solve_contact_support(self.spec)
        self.assertAlmostEqual(result["root_shift_up"], -0.01)
        self.assertAlmostEqual(result["contact_height_spread"], 0)
        self.assertAlmostEqual(result["support_area"], 0.32)
        self.assertEqual(result["balance_status"], "UNKNOWN_NO_COM")

    def test_measured_com_inside_outside_and_estimate_uncertainty(self):
        spec = copy.deepcopy(self.spec)
        spec["center_of_mass"] = {"position_armature_local": [0, 0, 1],
                                  "source": {"kind": "measured_mass", "reference": "measured_fixture"}}
        inside = solve_contact_support(spec)
        self.assertEqual(inside["balance_status"], "INSIDE_SUPPORT")
        self.assertGreater(inside["signed_edge_margin"], 0)
        spec["center_of_mass"]["position_armature_local"] = [2, 0, 1]
        outside = solve_contact_support(spec)
        self.assertEqual(outside["balance_status"], "OUTSIDE_SUPPORT")
        self.assertLess(outside["signed_edge_margin"], 0)
        spec["center_of_mass"]["source"]["kind"] = "human_estimate"
        self.assertEqual(solve_contact_support(spec)["balance_status"], "INDICATIVE_ESTIMATE")

    def test_single_foot_and_reversed_point_order(self):
        spec = copy.deepcopy(self.spec)
        spec["active_patch_ids"] = ["left"]
        spec["patches"][0]["points"].reverse()
        result = solve_contact_support(spec)
        self.assertAlmostEqual(result["support_area"], 0.08)

    def test_rejects_height_mismatch_and_degenerate_footprint(self):
        spec = copy.deepcopy(self.spec)
        spec["patches"][1]["points"][0]["position_armature_local"][2] = 0.1
        with self.assertRaisesRegex(ContractError, "ground plane"):
            solve_contact_support(spec)
        spec = copy.deepcopy(self.spec)
        for p in spec["patches"][0]["points"]:
            p["position_armature_local"][1] = 0
        spec["patches"][0]["points"][0]["position_armature_local"][0] = 0.3
        with self.assertRaisesRegex(ContractError, "collinear"):
            solve_contact_support(spec)

    def test_rejects_bad_ids_frame_and_stale_calibration(self):
        spec = copy.deepcopy(self.spec)
        spec["active_patch_ids"] = ["missing"]
        with self.assertRaisesRegex(ContractError, "unknown active"):
            solve_contact_support(spec)
        spec = copy.deepcopy(self.spec)
        spec["anatomical_frame"]["front"] = [0, 1, 0]
        with self.assertRaisesRegex(ContractError, "LEFT x UP"):
            solve_contact_support(spec)
        spec = copy.deepcopy(self.spec)
        calibration = {"rig_profile_id": spec["rig_profile_id"], "source": {"sha256": "b" * 64},
                       "anatomical_frame": spec["anatomical_frame"]}
        with self.assertRaisesRegex(ContractError, "digest mismatch"):
            solve_contact_support(spec, calibration)


if __name__ == "__main__":
    unittest.main()
