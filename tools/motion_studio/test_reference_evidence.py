import copy
import hashlib
import json
import pathlib
import sys
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from reference_evidence import validate_evidence  # noqa: E402
from validate import ContractError  # noqa: E402


def blank(source_id, obs_id, sample):
    return {"id": obs_id, "source_id": source_id, "sample": sample,
            "landmarks_2d": [], "landmarks_3d": [], "contact_hypotheses": [],
            "annotations": [{"kind": "phase", "text": "movement begins", "confidence": 0.7, "basis": "observed"}]}


class ReferenceEvidenceTests(unittest.TestCase):
    def setUp(self):
        digest = hashlib.sha256(b"synthetic reference bytes").hexdigest()
        self.evidence = {
            "schema_version": "0.2.0", "evidence_id": "fixture", "motion_id": "stumble_recovery_v0",
            "human_model_id": "canonical_human_v0",
            "sources": [
                {"id": "video", "kind": "video", "reference": "fixture.mov", "sha256": digest,
                 "timebase": {"fps_numerator": 30000, "fps_denominator": 1001, "first_frame": 1, "frame_count": 49},
                 "view": {"camera_side": "three_quarter", "mirrored": "unknown"}},
                {"id": "still", "kind": "image", "reference": "fixture.png", "sha256": digest,
                 "view": {"camera_side": "front", "mirrored": "no"}},
                {"id": "action", "kind": "blend_action", "reference": "fixture.blend#Runner_RIGAction", "sha256": digest,
                 "timebase": {"fps_numerator": 24, "fps_denominator": 1, "first_frame": 1, "frame_count": 49}},
                {"id": "prompt", "kind": "prompt", "reference": "prompt: right toe catches"},
            ],
            "observations": [
                blank("video", "video_1", {"frame": 1}),
                blank("video", "video_2", {"frame": 49}),
                blank("still", "still_1", {"static": True}),
                blank("action", "action_1", {"frame": 1}),
                blank("prompt", "prompt_1", {"static": True}),
            ],
        }
        self.evidence["observations"][0]["landmarks_2d"] = [
            {"landmark": "right_toe", "uv": [0.35, 0.92], "visibility": "visible", "confidence": 0.85},
            {"landmark": "left_heel", "visibility": "occluded", "confidence": 0.2},
        ]
        self.evidence["observations"][0]["contact_hypotheses"] = [
            {"landmark": "right_toe", "state": "touching", "surface": "ground", "confidence": 0.6, "basis": "visible"}
        ]
        self.evidence["observations"][3]["landmarks_3d"] = [
            {"landmark": "pelvis", "xyz": [0, 1, 0], "space": "source_armature_local", "unit": "source_unit", "confidence": 1}
        ]
        self.evidence["observations"][4]["annotations"] = [
            {"kind": "motion", "text": "right toe catches", "confidence": 1, "basis": "stated"}
        ]

    def assert_invalid(self, mutate, expected=None):
        evidence = copy.deepcopy(self.evidence)
        mutate(evidence)
        with self.assertRaises(ContractError) as captured:
            validate_evidence(evidence)
        if expected:
            self.assertIn(expected, str(captured.exception))

    def test_valid_multisource_and_prompt_example(self):
        self.assertIs(validate_evidence(self.evidence), self.evidence)
        example = json.loads((HERE / "examples/prompt_reference_v0_2.json").read_text(encoding="utf-8"))
        validate_evidence(example)

    def test_rejects_unknown_source_duplicate_id_or_unused_source(self):
        self.assert_invalid(lambda e: e["observations"][0].update(source_id="missing"), "unknown source")
        self.assert_invalid(lambda e: e["sources"][1].update(id="video"), "duplicate source")
        self.assert_invalid(lambda e: e["observations"].pop(), "each source")

    def test_rejects_frame_bounds_order_and_wrong_sampling(self):
        self.assert_invalid(lambda e: e["observations"][1]["sample"].update(frame=50), "outside source")
        self.assert_invalid(lambda e: e["observations"][1]["sample"].update(frame=0), "outside source")
        self.assert_invalid(lambda e: e["observations"].insert(1, blank("video", "video_earlier", {"frame": 1})), "duplicate sample")
        self.assert_invalid(lambda e: e["observations"][2].update(sample={"frame": 1}), "sample type")
        self.assert_invalid(lambda e: e["observations"][0].update(sample={"frame": 1, "static": True}), "exactly one")

    def test_video_depth_and_prompt_pose_cannot_be_claimed(self):
        point3d = copy.deepcopy(self.evidence["observations"][3]["landmarks_3d"][0])
        self.assert_invalid(lambda e: e["observations"][0]["landmarks_3d"].append(point3d), "3D landmarks")
        self.assert_invalid(lambda e: e["observations"][4]["landmarks_2d"].append({"landmark": "pelvis", "uv": [0.5, 0.5], "visibility": "visible", "confidence": 1}), "2D landmarks")
        self.assert_invalid(lambda e: e["observations"][4]["annotations"][0].update(basis="observed"), "visually observed")

    def test_visibility_contact_and_confidence_integrity(self):
        self.assert_invalid(lambda e: e["observations"][0]["landmarks_2d"][1].update(uv=[0.4, 0.5]), "occluded")
        self.assert_invalid(lambda e: e["observations"][0]["landmarks_2d"][0].update(confidence=1.2), "above maximum")
        self.assert_invalid(lambda e: e["observations"][0]["landmarks_2d"][0].pop("uv"), "need UV")
        self.assert_invalid(lambda e: e["observations"][0]["contact_hypotheses"][0].update(landmark="left_heel"), "visible contact")

    def test_source_identity_and_schema_version(self):
        self.assert_invalid(lambda e: e.update(schema_version="0.3.0"), "wrong constant")
        self.assert_invalid(lambda e: e["sources"][0].pop("sha256"), "media digest")
        self.assert_invalid(lambda e: e["sources"][0].pop("view"), "view required")
        self.assert_invalid(lambda e: e["sources"][2].pop("timebase"), "timebase required")


if __name__ == "__main__":
    unittest.main()
