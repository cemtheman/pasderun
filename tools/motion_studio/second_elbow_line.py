"""Solve a descending second-position elbow line with measured arm lengths."""

from __future__ import annotations

import math

from elbow_flexion import inward_flexion
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


def _circle_at_midheight(shoulder, wrist, upper, lower, up):
    """Both length-preserving elbow intersections at the requested height."""
    delta = sub(wrist, shoulder)
    distance = math.dist(wrist, shoulder)
    require(abs(upper - lower) + 1e-8 < distance < upper + lower - 1e-8,
            "second", "singular or unreachable arm")
    forward = _unit(delta)
    along = (upper * upper - lower * lower + distance * distance) / (2 * distance)
    radius = math.sqrt(max(0, upper * upper - along * along))
    center = add(shoulder, mul(forward, along))
    shoulder_up, wrist_up = dot(shoulder, up), dot(wrist, up)
    require(shoulder_up > wrist_up, "second", "shoulder must be above wrist")
    target_up = (shoulder_up + wrist_up) / 2
    up_axis = _unit(sub(up, mul(forward, dot(up, forward))))
    cosine = (target_up - dot(center, up)) / (radius * dot(up_axis, up))
    require(abs(cosine) <= 1 + 1e-6, "second", "mid-height elbow unreachable")
    cosine = max(-1.0, min(1.0, cosine))
    sideways_axis = _unit(_cross(forward, up_axis))
    base = add(center, mul(up_axis, radius * cosine))
    offset = mul(sideways_axis, radius * math.sqrt(max(0, 1 - cosine * cosine)))
    return add(base, offset), sub(base, offset)


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
        candidates = _circle_at_midheight(shoulder, wrist, upper, lower, up)
        shoulder_up, wrist_up = dot(shoulder, up), dot(wrist, up)
        chosen = min(candidates, key=lambda point: math.dist(point, elbow))
        require(shoulder_up > dot(chosen, up) > wrist_up, side, "elbow line not descending")
        require(abs(math.dist(chosen, shoulder) - upper) < 1e-6 and
                abs(math.dist(chosen, wrist) - lower) < 1e-6, side, "arm length changed")
        arms[side] = {**arm, "elbow": chosen}
    return {"pose_id": "second", "arms": arms}


def _side_turn_deg(shoulder, elbow, wrist, frame):
    a, b = sub(elbow, shoulder), sub(wrist, elbow)
    a = [dot(a, frame["front"]), dot(a, frame["up"])]
    b = [dot(b, frame["front"]), dot(b, frame["up"])]
    denominator = math.hypot(*a) * math.hypot(*b)
    require(denominator > 1e-9, "second", "degenerate side profile")
    return math.degrees(math.acos(max(-1, min(1, dot(a, b) / denominator))))


def solve_second_forward_line(solution: dict, frame: dict) -> tuple[dict, dict]:
    """Search reachable wrist targets for a descending, forward-moving side line.

    A bounded visual-probe criterion keeps a gentle bend: at most 20 degrees
    of projected side turn, at least 10 degrees of three-dimensional elbow bend.
    These are candidate shape criteria, never ballet technique thresholds.
    """
    require(solution["pose_id"] == "second", "second", "requires second pose")
    arms, diagnostics = {}, {}
    for side, arm in solution["arms"].items():
        shoulder, original_elbow, original_wrist = (arm[k] for k in ("shoulder", "elbow", "wrist"))
        upper = math.dist(shoulder, original_elbow)
        lower = math.dist(original_elbow, original_wrist)
        outward = frame["left"] if side == "left" else mul(frame["left"], -1)
        step = upper * .03
        feasible = []
        for inward_steps in range(0, 9):
            for forward_steps in range(0, 28):
                shift = add(mul(outward, -inward_steps * step),
                            mul(frame["front"], forward_steps * step))
                wrist = add(original_wrist, shift)
                distance = math.dist(shoulder, wrist)
                if distance >= upper + lower - 1e-8 or distance <= abs(upper - lower) + 1e-8:
                    continue
                try:
                    elbows = _circle_at_midheight(shoulder, wrist, upper, lower, frame["up"])
                except ValueError:
                    continue
                full_bend = math.degrees(math.acos(max(-1, min(1,
                    (distance * distance - upper * upper - lower * lower) / (-2 * upper * lower)))))
                # full_bend is the interior angle; keep at least a 10-degree bend.
                if full_bend > 170:
                    continue
                for elbow in elbows:
                    upper_front = dot(sub(elbow, shoulder), frame["front"])
                    lower_front = dot(sub(wrist, elbow), frame["front"])
                    if upper_front <= 0 or lower_front <= 0:
                        continue
                    turn = _side_turn_deg(shoulder, elbow, wrist, frame)
                    if turn > 20:
                        continue
                    candidate_arm = {"shoulder": shoulder, "elbow": elbow, "wrist": wrist}
                    inward = mul(outward, -1)
                    try:
                        flexion = inward_flexion(candidate_arm, inward, side)
                    except ValueError:
                        continue
                    feasible.append((math.sqrt(dot(shift, shift)), turn, inward_steps,
                                     forward_steps, elbow, wrist, shift, full_bend, flexion))
        require(feasible, side, "no reachable forward-moving gentle elbow line")
        _, turn, inward_steps, forward_steps, elbow, wrist, shift, full_bend, flexion = min(
            feasible, key=lambda c: (c[0], c[1]))
        arms[side] = {**arm, "elbow": elbow, "wrist": wrist,
                      "hand": add(arm["hand"], shift)}
        diagnostics[side] = {"inward_steps": inward_steps, "forward_steps": forward_steps,
                             "step_armature_units": round(step, 8),
                             "wrist_shift_armature_units": [round(x, 8) for x in shift],
                             "side_turn_deg": round(turn, 6),
                             "elbow_interior_deg": round(full_bend, 6),
                             "inward_flexion": flexion,
                             "upper_length": round(upper, 8), "lower_length": round(lower, 8)}
    return {"pose_id": "second", "arms": arms}, diagnostics
