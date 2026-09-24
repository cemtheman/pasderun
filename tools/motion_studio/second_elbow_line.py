"""Solve a descending second-position elbow line with measured arm lengths."""

from __future__ import annotations

import math

from schema_validation import require
from static_pose import add, dot, mul, sub


def _unit(vector):
    length = math.sqrt(dot(vector, vector))
    require(length > 1e-8, "second", "degenerate direction")
    return mul(vector, 1 / length)


def _cross(a, b):
    return [a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0]]


def solve_second_elbow_line(solution: dict, frame: dict) -> dict:
    """Choose the elbow-circle intersection at the shoulder/wrist mid-height.

    The closest intersection to the existing landmark retains its bend side.
    No bone angles, lengths, wrist targets or hand endpoints are invented.
    """
    require(solution["pose_id"] == "second", "second", "requires second pose")
    up = frame["up"]
    arms = {}
    for side, arm in solution["arms"].items():
        shoulder, elbow, wrist = (arm[name] for name in ("shoulder", "elbow", "wrist"))
        upper = math.dist(shoulder, elbow)
        lower = math.dist(elbow, wrist)
        delta = sub(wrist, shoulder)
        distance = math.dist(wrist, shoulder)
        require(abs(upper - lower) + 1e-8 < distance < upper + lower - 1e-8,
                side, "singular or unreachable arm")
        forward = _unit(delta)
        along = (upper * upper - lower * lower + distance * distance) / (2 * distance)
        radius = math.sqrt(max(0, upper * upper - along * along))
        center = add(shoulder, mul(forward, along))
        shoulder_up, wrist_up = dot(shoulder, up), dot(wrist, up)
        require(shoulder_up > wrist_up, side, "shoulder must be above wrist")
        target_up = (shoulder_up + wrist_up) / 2
        up_perpendicular = sub(up, mul(forward, dot(up, forward)))
        up_axis = _unit(up_perpendicular)
        max_vertical = radius * dot(up_axis, up)
        require(max_vertical > 1e-8, side, "no vertical elbow freedom")
        cosine = (target_up - dot(center, up)) / max_vertical
        require(abs(cosine) <= 1 + 1e-6, side, "mid-height elbow unreachable")
        cosine = max(-1.0, min(1.0, cosine))
        sideways_axis = _unit(_cross(forward, up_axis))
        perpendicular = radius * math.sqrt(max(0, 1 - cosine * cosine))
        base = add(center, mul(up_axis, radius * cosine))
        candidates = [add(base, mul(sideways_axis, sign * perpendicular)) for sign in (-1, 1)]
        chosen = min(candidates, key=lambda point: math.dist(point, elbow))
        require(shoulder_up > dot(chosen, up) > wrist_up, side, "elbow line not descending")
        require(abs(math.dist(chosen, shoulder) - upper) < 1e-6 and
                abs(math.dist(chosen, wrist) - lower) < 1e-6, side, "arm length changed")
        arms[side] = {**arm, "elbow": chosen}
    return {"pose_id": "second", "arms": arms}
