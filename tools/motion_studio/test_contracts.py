import copy
import importlib.util
import json
import pathlib
import unittest


HERE = pathlib.Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("motion_studio_validate", HERE / "validate.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
validate = module.validate
ContractError = module.ContractError


class ContractsV0Tests(unittest.TestCase):
    def setUp(self):
        self.motion = json.loads((HERE / "examples" / "stumble_recovery_v0.json").read_text(encoding="utf-8"))

    def test_minimal_motion_and_human_model(self):
        model = json.loads((HERE / "canonical_human_v0.json").read_text(encoding="utf-8"))
        self.assertIs(validate("human_model", model), model)
        minimal = {key: copy.deepcopy(self.motion[key]) for key in (
            "schema_version", "motion_id", "human_model_id", "fps", "duration_frames",
            "provenance", "phases", "markers", "landmark_targets", "contacts", "support", "constraints"
        )}
        minimal["phases"] = [{"id": "plie", "start_frame": 0, "end_frame": 49, "action": "plie to releve", "support_leg": "both", "gesture_leg": "none"}]
        minimal["contacts"] = []
        minimal["support"] = [{"start_frame": 0, "end_frame": 49, "contact_ids": []}]
        minimal["constraints"] = [{"kind": "knee_tracking", "phase_id": "plie", "intent": "knees track over toes"}, {"kind": "releve", "intent": "rise with controlled balance"}]
        minimal["markers"] = []
        self.assertIs(validate("motion_spec", minimal), minimal)
        self.assertIs(validate("motion_spec", self.motion), self.motion)

    def test_missing_required_and_version_are_rejected(self):
        for mutation in (lambda m: m.pop("fps"), lambda m: m.update(schema_version="0.2.0"), lambda m: m.update(fps=True)):
            m = copy.deepcopy(self.motion)
            mutation(m)
            with self.assertRaises(ContractError):
                validate("motion_spec", m)

    def test_markers_and_phases_must_be_ordered_and_bounded(self):
        m = copy.deepcopy(self.motion)
        m["markers"][0]["frame"] = 20
        with self.assertRaisesRegex(ContractError, "markers"):
            validate("motion_spec", m)
        m = copy.deepcopy(self.motion)
        m["phases"][1]["start_frame"] = 7
        with self.assertRaisesRegex(ContractError, "phases"):
            validate("motion_spec", m)

    def test_support_requires_existing_load_bearing_spanning_contact(self):
        for edit in (
            lambda m: m["support"][0].update(contact_ids=["missing"]),
            lambda m: m["contacts"][0].update(end_frame=8),
            lambda m: m["contacts"][0].update(mode="touch"),
            lambda m: m["contacts"][0].update(landmark="right_hand"),
        ):
            m = copy.deepcopy(self.motion)
            edit(m)
            with self.assertRaises(ContractError):
                validate("motion_spec", m)

    def test_landmark_targets_are_finite_and_unique(self):
        m = copy.deepcopy(self.motion)
        t = {"frame": 7, "landmark": "pelvis", "position": [0, 0.5, 0.1]}
        m["landmark_targets"] = [t, copy.deepcopy(t)]
        with self.assertRaisesRegex(ContractError, "duplicate target"):
            validate("motion_spec", m)
        m["landmark_targets"] = [{**t, "position": [0, float("nan"), 0]}]
        with self.assertRaisesRegex(ContractError, "finite"):
            validate("motion_spec", m)

    def test_rig_profile_frame_and_mapping(self):
        rig = {
            "schema_version": "0.1.0", "profile_id": "low_poly_girl_v0",
            "human_model_id": "canonical_human_v0",
            "source_glb": "assets/characters/low_poly_girl/low_poly_girl .glb",
            "armature": "Rig", "calibration_seed": "assets/characters/low_poly_girl/ballet_rig_calibration_seed_v1.json",
            "anatomical_frame": {"up": [0, 0, 1], "left": [1, 0, 0], "front": [0, -1, 0]},
            "landmark_bones": {"pelvis": "Hips", "left_toe": "Toes_L"},
        }
        validate("rig_profile", rig)
        bad = copy.deepcopy(rig)
        bad["anatomical_frame"]["front"] = [1, 0, 0]
        with self.assertRaises(ContractError):
            validate("rig_profile", bad)
        bad = copy.deepcopy(rig)
        bad["landmark_bones"]["imaginary"] = "Bone"
        with self.assertRaises(ContractError):
            validate("rig_profile", bad)

    def test_provenance_qa_and_asset_review(self):
        m = copy.deepcopy(self.motion)
        m["provenance"] = [{"kind": "video", "reference": "clip.mp4", "sha256": "g" * 64}]
        with self.assertRaises(ContractError):
            validate("motion_spec", m)
        qa = {"schema_version": "0.1.0", "motion_id": "plie_v0", "status": "pass", "checks": [{"name": "contact", "status": "fail", "evidence": "left foot slides"}]}
        with self.assertRaises(ContractError):
            validate("qa_result", qa)
        qa["status"] = "fail"
        validate("qa_result", qa)
        asset = {
            "schema_version": "0.1.0", "motion_id": "plie_v0", "spec_sha256": "a" * 64,
            "rig_profile_id": "low_poly_girl_v0", "qa_result_ref": "qa/plie.json",
            "review_status": "approved", "reviewers": [],
            "provenance": [{"kind": "teacher_refinement", "reference": "review-1"}],
        }
        with self.assertRaises(ContractError):
            validate("asset_metadata", asset)
        asset["reviewers"] = ["ballet_teacher"]
        validate("asset_metadata", asset)


if __name__ == "__main__":
    unittest.main()
