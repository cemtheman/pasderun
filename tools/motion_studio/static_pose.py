"""Deterministic two-link arm landmark solve; no bone-space angle authoring."""

from __future__ import annotations

import json
import math
from pathlib import Path

from schema_validation import require, shape


SCHEMA = json.loads(Path(__file__).with_name("static_pose_v0_3.schema.json").read_text(encoding="utf-8"))


def add(a, b):
    return [x + y for x, y in zip(a, b)]


def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def mul(a, scalar):
    return [x * scalar for x in a]


def dot(a, b):
    return sum(x * y for x, y in zip(a, b))


def length(a):
    return math.sqrt(dot(a, a))


def unit(a, where):
    size = length(a)
    require(size > 1e-8, where, "degenerate vector")
    return mul(a, 1 / size)


def validate_target_spec(spec, calibration):
    shape(spec, SCHEMA, "static_pose", SCHEMA["$defs"])
    require(spec["rig_profile_id"] == calibration["rig_profile_id"], "static_pose", "rig profile mismatch")
    sides = [target["side"] for target in spec["targets"]]
    require(len(sides) == len(set(sides)), "static_pose", "duplicate arm side")
    for target in spec["targets"]:
        require(target["landmark"] == f"{target['side']}_wrist", "static_pose", "landmark and side disagree")
    return spec


def solve_two_link(shoulder, elbow_rest, wrist_rest, wrist_goal, pole, where="arm"):
    """Joint centers and explicit bend plane; reject unreachable or singular cases."""
    upper = length(sub(elbow_rest, shoulder))
    lower = length(sub(wrist_rest, elbow_rest))
    require(upper > 1e-8 and lower > 1e-8, where, "zero-length joint segment")
    direction = sub(wrist_goal, shoulder)
    distance = length(direction)
    require(abs(upper - lower) + 1e-6 < distance < upper + lower - 1e-6,
            where, "target unreachable or straight/folded singularity")
    forward = unit(direction, where)
    pole_perp = sub(pole, mul(forward, dot(pole, forward)))
    bend = unit(pole_perp, where)
    along = (upper*upper - lower*lower + distance*distance) / (2 * distance)
    across = math.sqrt(max(0, upper*upper - along*along))
    elbow = add(shoulder, add(mul(forward, along), mul(bend, across)))
    require(abs(length(sub(elbow, shoulder)) - upper) < 1e-6, where, "upper length changed")
    require(abs(length(sub(wrist_goal, elbow)) - lower) < 1e-6, where, "lower length changed")
    return {"shoulder": shoulder, "elbow": elbow, "wrist": wrist_goal,
            "upper_length": upper, "lower_length": lower,
            "bend_plane_projection": dot(sub(elbow, shoulder), bend)}


def solve_static_pose(spec, calibration):
    validate_target_spec(spec, calibration)
    frame = calibration["anatomical_frame"]
    bones = calibration["canonical_bones"]
    result = {}
    for target in spec["targets"]:
        side = target["side"]
        shoulder = bones[f"{side}_upper_arm"]["head_local"]
        elbow = bones[f"{side}_forearm"]["head_local"]
        wrist = bones[f"{side}_hand"]["head_local"]
        reach = length(sub(elbow, shoulder)) + length(sub(wrist, elbow))
        left, up, front = target["offset_body_arm_reach"]
        delta = [reach * (left*frame["left"][i] + up*frame["up"][i] + front*frame["front"][i]) for i in range(3)]
        pole_axis = {
            "body_front": frame["front"], "body_back": mul(frame["front"], -1),
            "body_up": frame["up"], "body_down": mul(frame["up"], -1),
        }[target["bend_plane"]]
        goal = add(add(shoulder, mul(sub(wrist, shoulder), target["reach_fraction"])), delta)
        solved = solve_two_link(shoulder, elbow, wrist, goal, pole_axis, side)
        solved["wrist_rest"] = wrist
        solved["arm_reach"] = reach
        solved["bone_names"] = [bones[f"{side}_upper_arm"]["rig_bone"],
                                bones[f"{side}_forearm"]["rig_bone"],
                                bones[f"{side}_hand"]["rig_bone"]]
        result[side] = solved
    return {"pose_id": spec["pose_id"], "rig_profile_id": spec["rig_profile_id"],
            "source_glb_sha256": calibration["source"]["sha256"], "arms": result}
