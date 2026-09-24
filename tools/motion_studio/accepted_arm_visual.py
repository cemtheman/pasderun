"""Convert accepted body landmarks to calibrated final-Rig joint targets.

This is a coordinate change, not rotation retargeting or ballet pose approval.
"""

from __future__ import annotations

import math

from accepted_arm_reference import JOINTS, SCHEMA
from schema_validation import require, shape
from static_pose import dot


def joint_targets(reference: dict, calibration: dict, pose_name: str) -> dict:
    shape(reference, SCHEMA, "accepted_reference", SCHEMA["$defs"])
    require(reference["source_glb_sha256"] == calibration["source"]["sha256"],
            "accepted_reference", "calibrated GLB digest mismatch")
    require(pose_name in ("bras_bas", "en_avant", "second"), "pose", "unknown accepted pose")
    pose = reference["poses"][pose_name]
    require(set(pose) == set(JOINTS), "pose", "arm landmark inventory mismatch")
    bones = calibration["canonical_bones"]
    frame = calibration["anatomical_frame"]
    origin = bones["pelvis"]["head_local"]
    height = dot(bones["head"]["head_local"], frame["up"]) - sum(
        dot(bones[f"{side}_foot"]["head_local"], frame["up"]) for side in ("left", "right")) / 2
    require(height > 0, "calibration", "degenerate standing height")

    def to_local(body_point: list[float]) -> list[float]:
        return [origin[i] + height * sum(body_point[j] * frame[axis][i]
                                       for j, axis in enumerate(("left", "up", "front")))
                for i in range(3)]

    arms = {}
    for side in ("left", "right"):
        names = [bones[f"{side}_{joint}"]["rig_bone"] for joint in ("shoulder", "elbow", "wrist")]
        points = {joint: to_local(pose[f"{side}_{joint}"])
                  for joint in ("shoulder", "elbow", "wrist", "hand")}
        reach = sum(bones[f"{side}_{joint}"]["length"] for joint in ("shoulder", "elbow"))
        require(math.isfinite(reach) and reach > 0, side, "invalid arm reach")
        for (a, b), length in zip((("shoulder", "elbow"), ("elbow", "wrist")),
                                  (bones[f"{side}_shoulder"]["length"], bones[f"{side}_elbow"]["length"])):
            actual = math.dist(points[a], points[b])
            require(abs(actual - length) <= reach * 0.005, side,
                    f"{a}-{b} length {actual:.6f} differs from calibrated Rig {length:.6f}")
        arms[side] = {**points, "bone_names": names, "arm_reach": reach}
    return {"pose_id": pose_name, "arms": arms}
