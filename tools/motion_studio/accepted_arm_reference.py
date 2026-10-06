"""Extract accepted Phase 10 canonical landmark geometry as read-only evidence.

The previous solver and retargeting implementation are never imported or run.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from schema_validation import require, shape
from static_pose import dot
from port_de_bras_qa import evaluate_port_de_bras


SCHEMA = json.loads(Path(__file__).with_name("accepted_arm_reference_v0_6.schema.json").read_text(encoding="utf-8"))
JOINTS = tuple(f"{side}_{joint}" for side in ("left", "right")
               for joint in ("shoulder", "elbow", "wrist", "hand"))


def extract_accepted_arm_reference(raw: bytes, calibration: dict) -> dict:
    source = json.loads(raw)
    require(source.get("phase") == "10.6.5", "accepted_reference", "wrong source phase")
    require(source.get("inputs", {}).get("source_glb_sha256") == calibration["source"]["sha256"],
            "accepted_reference", "source GLB digest mismatch")
    gate = source.get("foundation_gate", {})
    require(gate.get("all_pose_geometry_pass") is True and gate.get("all_pose_joint_dofs_preferred") is True,
            "accepted_reference", "source geometry gate did not pass")
    bones = calibration["canonical_bones"]
    frame = calibration["anatomical_frame"]
    head = bones["head"]["head_local"]
    feet = [bones[f"{side}_foot"]["head_local"] for side in ("left", "right")]
    height = dot(head, frame["up"]) - sum(dot(foot, frame["up"]) for foot in feet) / 2
    require(height > 0, "accepted_reference", "degenerate standing height")
    poses = {}
    for pose_name in ("bras_bas", "en_avant", "second"):
        solution = source.get("solutions", {}).get(pose_name, {})
        require(solution.get("validation", {}).get("status") == "PASS" and
                solution.get("evidence", {}).get("preferred_joint_envelope") == "PASS",
                pose_name, "source pose did not pass its gates")
        landmarks = solution.get("state", {}).get("landmarks", {})
        require(set(JOINTS).issubset(landmarks), pose_name, "missing arm landmarks")
        poses[pose_name] = {}
        for joint in JOINTS:
            point = landmarks[joint]
            require(isinstance(point, dict) and set(point) == {"left", "up", "front"},
                    joint, "expected three declared body coordinates")
            poses[pose_name][joint] = [point[axis] / height for axis in ("left", "up", "front")]
    result = {"schema_version": "0.6.1", "reference_id": "phase10_6_foundation_arm_landmarks",
              "source_profile_sha256": hashlib.sha256(raw).hexdigest(),
              "source_glb_sha256": calibration["source"]["sha256"],
              "coordinate_space": "body_relative", "position_unit": "standing_height", "poses": poses}
    shape(result, SCHEMA, "accepted_reference", SCHEMA["$defs"])
    for pose_name, landmarks in poses.items():
        require(set(landmarks) == set(JOINTS), pose_name, "unexpected arm landmark inventory")
    return result


def review_accepted_reference(reference: dict) -> dict:
    """Compare inherited arm landmarks to the user reference without approving it."""
    shape(reference, SCHEMA, "accepted_reference", SCHEMA["$defs"])
    poses = {}
    for stage, source in (("start", "bras_bas"), ("middle", "en_avant"), ("end", "second")):
        landmarks = reference["poses"][source]
        require(set(landmarks) == set(JOINTS), stage, "wrong arm landmark inventory")
        poses[stage] = {"arms": {side: {joint: landmarks[f"{side}_{joint}"]
                                         for joint in ("shoulder", "elbow", "wrist")}
                                 for side in ("left", "right")}}
    result = evaluate_port_de_bras(poses, {"left": [1, 0, 0], "up": [0, 1, 0], "front": [0, 0, 1]})
    result["source_profile_sha256"] = reference["source_profile_sha256"]
    result["source_glb_sha256"] = reference["source_glb_sha256"]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--review-output", type=Path)
    args = parser.parse_args()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    result = extract_accepted_arm_reference(args.source.read_bytes(), calibration)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"MOTION_STUDIO_ACCEPTED_ARM_REFERENCE=PASS {args.output}")
    if args.review_output:
        review = review_accepted_reference(result)
        args.review_output.parent.mkdir(parents=True, exist_ok=True)
        args.review_output.write_text(json.dumps(review, indent=2) + "\n", encoding="utf-8")
        print(f"PORT_DE_BRAS_GEOMETRY_REVIEW={review['status']} {args.review_output}")


if __name__ == "__main__":
    main()
