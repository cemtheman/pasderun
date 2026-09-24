import copy
import hashlib
import json
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from temporal import sample_timeline  # noqa: E402
from validate import ContractError  # noqa: E402


class TemporalTests(unittest.TestCase):
    def setUp(self):
        self.raw = (HERE / "examples/stumble_recovery_v0.json").read_bytes()
        self.request = {"schema_version": "0.5.0", "motion_id": "stumble_recovery_v0",
                        "motion_spec_sha256": hashlib.sha256(self.raw).hexdigest(),
                        "sample_frames": [0, 10, 11, 17, 18, 25, 26, 48]}

    def test_half_open_contact_and_support_transitions(self):
        samples = sample_timeline(self.raw, self.request)["samples"]
        self.assertEqual(samples[1]["support_contact_ids"], ["right_initial"])
        self.assertEqual(samples[2]["support_contact_ids"], [])
        self.assertEqual(samples[2]["active_contact_ids"], [])
        self.assertEqual(samples[4]["support_contact_ids"], ["left_catch"])
        self.assertEqual(samples[4]["marker_ids"], ["left_catch"])
        self.assertEqual(samples[6]["support_contact_ids"], ["right_recovery"])
        self.assertEqual(samples[-1]["phase_id"], "stable_run")

    def test_rejects_stale_input_version_and_out_of_bounds(self):
        request = copy.deepcopy(self.request)
        request["motion_spec_sha256"] = "0" * 64
        with self.assertRaisesRegex(ContractError, "digest mismatch"):
            sample_timeline(self.raw, request)
        request = copy.deepcopy(self.request)
        request["schema_version"] = "0.6.0"
        with self.assertRaisesRegex(ContractError, "wrong constant"):
            sample_timeline(self.raw, request)
        request = copy.deepcopy(self.request)
        request["sample_frames"].append(49)
        with self.assertRaisesRegex(ContractError, "outside duration"):
            sample_timeline(self.raw, request)
        request["sample_frames"] = [10, 0]
        with self.assertRaisesRegex(ContractError, "ordered"):
            sample_timeline(self.raw, request)

    def test_explicit_landmarks_only_and_motion_identity(self):
        data = json.loads(self.raw)
        data["landmark_targets"] = [{"frame": 18, "landmark": "left_ankle", "position": [0.1, 0.2, 0.3]}]
        raw = (json.dumps(data) + "\n").encode()
        request = copy.deepcopy(self.request)
        request["motion_spec_sha256"] = hashlib.sha256(raw).hexdigest()
        result = sample_timeline(raw, request)
        self.assertEqual(result["samples"][4]["landmark_targets"], data["landmark_targets"])
        self.assertTrue(all(not sample["landmark_targets"] for i, sample in enumerate(result["samples"]) if i != 4))
        request["motion_id"] = "other"
        with self.assertRaisesRegex(ContractError, "motion ID mismatch"):
            sample_timeline(raw, request)


if __name__ == "__main__":
    unittest.main()
