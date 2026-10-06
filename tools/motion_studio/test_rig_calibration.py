import copy
import hashlib
import json
import pathlib
import sys
import tempfile
import unittest


HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from rig_calibration import ContractError, build, validate_calibration  # noqa: E402
from validate import validate  # noqa: E402


CANONICAL = [
    "pelvis", "spine_lower", "spine_mid", "chest", "neck", "head",
    "left_clavicle", "right_clavicle", "left_upper_arm", "right_upper_arm",
    "left_forearm", "right_forearm", "left_hand", "right_hand", "left_middle", "right_middle",
    "left_thigh", "right_thigh", "left_shin", "right_shin", "left_foot", "right_foot", "left_toes", "right_toes",
]


class RigCalibrationContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = pathlib.Path(self.temp.name)
        source_path = self.repo / "assets/characters/low_poly_girl/low_poly_girl .glb"
        seed_path = self.repo / "assets/characters/low_poly_girl/ballet_rig_calibration_seed_v1.json"
        source_path.parent.mkdir(parents=True)
        source_path.write_bytes(b"synthetic rig fixture; no Blender measurements")
        mapping = {name: f"Bone_{name}" for name in CANONICAL}
        segments = {
            "left_hand_tangent": [mapping["left_hand"], mapping["left_middle"]],
            "right_hand_tangent": [mapping["right_hand"], mapping["right_middle"]],
            "left_foot_forward": [mapping["left_foot"], mapping["left_toes"]],
            "right_foot_forward": [mapping["right_foot"], mapping["right_toes"]],
        }
        self.seed = {
            "schema_version": 1, "profile_id": "synthetic_seed",
            "source_glb": str(source_path.relative_to(self.repo)), "expected_armature_name": "Rig",
            "coordinate_space": "BLENDER_ARMATURE_LOCAL",
            "declared_anatomical_frame": {"up": [0, 0, 1], "left": [1, 0, 0], "front": [0, -1, 0]},
            "canonical_bones": mapping, "semantic_segments": segments,
        }
        seed_path.write_text(json.dumps(self.seed), encoding="utf-8")
        self.rig = {
            "schema_version": "0.1.0", "profile_id": "synthetic_rig", "human_model_id": "canonical_human_v0",
            "source_glb": str(source_path.relative_to(self.repo)), "armature": "Rig",
            "calibration_seed": str(seed_path.relative_to(self.repo)),
            "anatomical_frame": self.seed["declared_anatomical_frame"], "landmark_bones": {"pelvis": mapping["pelvis"]},
        }
        bones = {}
        for i, (canonical, rig_name) in enumerate(mapping.items()):
            head, tail = [0, 0, i], [0, 1, i]
            bones[canonical] = {
                "rig_bone": rig_name, "parent": None if i == 0 else mapping[CANONICAL[i-1]],
                "length": 1.0, "head_local": head, "tail_local": tail,
                "matrix_local": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, i], [0, 0, 0, 1]],
                "rest_axes": {"x": [1, 0, 0], "y_length": [0, 1, 0], "z": [0, 0, 1]},
            }
        self.source = {
            "phase": "10.6.1", "schema_version": 1, "profile_id": self.seed["profile_id"],
            "validation": {"passed": True},
            "frame_policy": {"body_front_is_declared": True, "body_front_is_inferred_from_toes": False, "pose_dependent_frame_allowed": False},
            "source": {"path": self.rig["source_glb"], "armature": "Rig", "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest()},
            "coordinate_space": self.seed["coordinate_space"],
            "declared_anatomical_frame": self.seed["declared_anatomical_frame"],
            "canonical_bones": bones,
            "semantic_segments": {name: {"start_bone": a, "end_bone": b, "direction_local": [0, 0, 1]}
                                  for name, (a, b) in segments.items()},
        }

    def test_profile_contract_and_bridge(self):
        validate("rig_profile", self.rig)
        output = build(self.repo, self.rig, self.seed, self.source)
        self.assertEqual(output["source"]["sha256"], self.source["source"]["sha256"])
        self.assertEqual(len(output["canonical_bones"]), 24)
        self.assertEqual(output["unresolved"], ["joint_limits", "bend_planes", "contact_geometry", "landmark_offsets", "center_of_mass"])
        self.assertIs(validate_calibration(output, self.rig, self.seed, self.repo), output)

    def test_source_hash_change_is_rejected(self):
        output = build(self.repo, self.rig, self.seed, self.source)
        (self.repo / self.rig["source_glb"]).write_bytes(b"changed rig")
        with self.assertRaisesRegex(ContractError, "source.*SHA-256"):
            validate_calibration(output, self.rig, self.seed, self.repo)

    def test_seed_change_is_rejected(self):
        output = build(self.repo, self.rig, self.seed, self.source)
        (self.repo / self.rig["calibration_seed"]).write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ContractError, "seed.*SHA-256"):
            validate_calibration(output, self.rig, self.seed, self.repo)

    def test_bad_frame_or_bone_geometry_is_rejected(self):
        for mutate in (
            lambda x: x["anatomical_frame"].update(front=[0, 1, 0]),
            lambda x: x["canonical_bones"]["left_shin"].update(length=2),
            lambda x: x["canonical_bones"]["left_shin"]["rest_axes"].update(z=[0, 0, -1]),
            lambda x: x["canonical_bones"]["left_shin"]["matrix_local"][0].__setitem__(3, 3),
        ):
            output = copy.deepcopy(build(self.repo, self.rig, self.seed, self.source))
            mutate(output)
            with self.assertRaises(ContractError):
                validate_calibration(output, self.rig, self.seed, self.repo)

    def test_missing_bone_or_wrong_segment_is_rejected(self):
        output = build(self.repo, self.rig, self.seed, self.source)
        output["canonical_bones"].pop("right_toes")
        with self.assertRaises(ContractError):
            validate_calibration(output, self.rig, self.seed, self.repo)
        output = build(self.repo, self.rig, self.seed, self.source)
        output["semantic_segments"]["right_foot_forward"]["direction_local"] = [1, 0, 0]
        with self.assertRaises(ContractError):
            validate_calibration(output, self.rig, self.seed, self.repo)

    def test_parent_cycle_is_rejected(self):
        output = build(self.repo, self.rig, self.seed, self.source)
        output["canonical_bones"]["left_shin"]["parent"] = self.seed["canonical_bones"]["right_shin"]
        output["canonical_bones"]["right_shin"]["parent"] = self.seed["canonical_bones"]["left_shin"]
        with self.assertRaisesRegex(ContractError, "parent cycle"):
            validate_calibration(output, self.rig, self.seed, self.repo)

    def test_rejects_false_phase10_pass_or_weakened_front_policy(self):
        source = copy.deepcopy(self.source)
        source["validation"]["passed"] = False
        with self.assertRaises(ContractError):
            build(self.repo, self.rig, self.seed, source)
        source = copy.deepcopy(self.source)
        source["frame_policy"]["body_front_is_inferred_from_toes"] = True
        with self.assertRaises(ContractError):
            build(self.repo, self.rig, self.seed, source)

    def test_rejects_claiming_unmeasured_fields(self):
        output = build(self.repo, self.rig, self.seed, self.source)
        output["unresolved"].remove("contact_geometry")
        with self.assertRaises(ContractError):
            validate_calibration(output, self.rig, self.seed, self.repo)


if __name__ == "__main__":
    unittest.main()
