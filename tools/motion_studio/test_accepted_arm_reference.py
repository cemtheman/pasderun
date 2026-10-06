import copy
import json
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from accepted_arm_reference import JOINTS, extract_accepted_arm_reference, review_accepted_reference  # noqa: E402
from validate import ContractError  # noqa: E402


class AcceptedArmReferenceTests(unittest.TestCase):
    def setUp(self):
        self.calibration = {
            "source": {"sha256": "a" * 64},
            "anatomical_frame": {"up": [0, 0, 1], "left": [1, 0, 0], "front": [0, -1, 0]},
            "canonical_bones": {"head": {"head_local": [0, 0, 2]},
                                "left_foot": {"head_local": [0, 0, 0]},
                                "right_foot": {"head_local": [0, 0, 0]}}}
        solution = lambda: {"validation": {"status": "PASS"},
                            "evidence": {"preferred_joint_envelope": "PASS"},
                            "state": {"landmarks": {name: {"left": 0.4, "up": 1.2, "front": 0.2}
                                                    for name in JOINTS}}}
        self.source = {"phase": "10.6.5", "inputs": {"source_glb_sha256": "a" * 64},
                       "foundation_gate": {"all_pose_geometry_pass": True, "all_pose_joint_dofs_preferred": True},
                       "solutions": {p: solution() for p in ("bras_bas", "en_avant", "second")}}

    def extract(self, source=None, calibration=None):
        return extract_accepted_arm_reference(json.dumps(source or self.source).encode(), calibration or self.calibration)

    def test_normalizes_all_joint_centers_in_body_frame_with_digest(self):
        result = self.extract()
        self.assertEqual(result["schema_version"], "0.6.1")
        self.assertEqual(result["poses"]["second"]["left_elbow"], [0.2, 0.6, 0.1])
        self.assertEqual(set(result["poses"]), {"bras_bas", "en_avant", "second"})
        self.assertEqual(len(result["source_profile_sha256"]), 64)

    def test_rejects_stale_glb_failed_gate_and_missing_pose_landmark(self):
        source = copy.deepcopy(self.source)
        source["inputs"]["source_glb_sha256"] = "b" * 64
        with self.assertRaisesRegex(ContractError, "digest mismatch"):
            self.extract(source)
        source = copy.deepcopy(self.source)
        source["solutions"]["second"]["validation"]["status"] = "FAIL"
        with self.assertRaisesRegex(ContractError, "source pose did not pass"):
            self.extract(source)
        source = copy.deepcopy(self.source)
        del source["solutions"]["bras_bas"]["state"]["landmarks"]["left_elbow"]
        with self.assertRaisesRegex(ContractError, "missing arm landmarks"):
            self.extract(source)

    def test_accepted_profile_does_not_bypass_new_visual_relationships(self):
        # All old per-pose gates pass, yet three identical poses cannot open arms.
        reference = self.extract()
        review = review_accepted_reference(reference)
        self.assertEqual(review["status"], "fail")
        self.assertIn("left_wrist_opens_outward",
                      {c["name"] for c in review["checks"] if c["status"] == "fail"})


if __name__ == "__main__":
    unittest.main()
