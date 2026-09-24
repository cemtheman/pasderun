"""Unreviewed guide arm shapes built from calibrated, length-preserving landmarks."""

from __future__ import annotations

import math
from collections import deque

from elbow_flexion import inward_flexion
from schema_validation import require
from static_pose import add, dot, length, mul, solve_two_link, sub, unit


def crown_position(second: dict, anatomical_frame: dict, head_top_height: float,
                   lateral_fraction: float = .12) -> dict:
    """Construct a bounded overhead oval. Height is a rig-bone proxy, not skin evidence."""
    require(second["pose_id"] == "second", "crown", "requires reviewed second source")
    require(math.isfinite(head_top_height), "crown", "invalid calibrated head height")
    require(math.isfinite(lateral_fraction) and .08 <= lateral_fraction <= .3,
            "crown", "invalid overhead wrist separation")
    result = {}
    for side in ("left", "right"):
        arm = second["arms"][side]
        shoulder = arm["shoulder"]
        reach = math.dist(shoulder, arm["elbow"]) + math.dist(arm["elbow"], arm["wrist"])
        hand_length = math.dist(arm["wrist"], arm["hand"])
        up, front, left = (anatomical_frame[k] for k in ("up", "front", "left"))
        outward = left if side == "left" else mul(left, -1)
        lateral = max(hand_length * 1.6, reach * lateral_fraction)
        height = min(head_top_height + .04 * reach, dot(shoulder, up) + .72 * reach)
        require(height > dot(shoulder, up) + .32 * reach, side,
                "head proxy cannot reach an overhead wrist")
        # Body-center wrist offset gives an overhead oval; keep the crown in
        # front of the face rather than hiding it behind the head mesh.
        wrist = add(mul(outward, lateral), add(mul(up, height),
                    mul(front, dot(shoulder, front) + reach * .25)))
        solved = solve_two_link(shoulder, arm["elbow"], arm["wrist"],
                                wrist, outward, side)
        direction = unit(add(mul(outward, -.85), add(mul(front, .15), mul(up, .15))), side)
        hand = add(wrist, mul(direction, hand_length))
        crowned = {**arm, "elbow": solved["elbow"], "wrist": wrist, "hand": hand}
        inward_flexion(crowned, mul(outward, -1), side)
        result[side] = crowned
    return {"pose_id": "fifth_crown_candidate", "arms": result}


def combine_arm_positions(name: str, left_pose: dict, right_pose: dict) -> dict:
    """Guide third/fourth are explicitly asymmetric arm combinations."""
    require(name in ("third_left_first", "third_right_first",
                     "fourth_left_crown", "fourth_right_crown"),
            "mixed", "unsupported named guide combination")
    a, b = left_pose["arms"]["left"], right_pose["arms"]["right"]
    require(math.dist(a["shoulder"], b["shoulder"]) > 1e-5,
            "mixed", "arm sides must differ")
    return {"pose_id": name, "arms": {"left": a.copy(), "right": b.copy()}}


def sample_arm_transition(start: dict, end: dict, frame: dict,
                          count: int = 25) -> list[dict]:
    """Keyable joint targets; endpoints exact and interior lengths preserved."""
    require(isinstance(count, int) and count >= 3, "transition", "invalid review grid")
    result = []
    for index in range(count):
        t = index / (count - 1)
        eased = t * t * (3 - 2 * t)
        arms, flexion = {}, {}
        for side in ("left", "right"):
            a, b = start["arms"][side], end["arms"][side]
            shoulder = a["shoulder"]
            require(math.dist(shoulder, b["shoulder"]) < 1e-7,
                    side, "reference shoulder changed")
            for j, k in (("shoulder", "elbow"), ("elbow", "wrist"), ("wrist", "hand")):
                require(abs(math.dist(a[j], a[k]) - math.dist(b[j], b[k])) < 1e-5,
                        side, "reference bone length changed")
            if index == 0:
                arm = a.copy()
            elif index == count - 1:
                arm = b.copy()
            else:
                wrist = add(mul(a["wrist"], 1 - eased), mul(b["wrist"], eased))
                pole = add(mul(sub(a["elbow"], shoulder), 1 - eased),
                           mul(sub(b["elbow"], shoulder), eased))
                elbow = solve_two_link(shoulder, a["elbow"], a["wrist"], wrist, pole, side)["elbow"]
                tip = add(mul(sub(a["hand"], a["wrist"]), 1 - eased),
                          mul(sub(b["hand"], b["wrist"]), eased))
                require(length(tip) > 1e-8, side, "hand tip direction vanished")
                arm = {**a, "elbow": elbow, "wrist": wrist,
                       "hand": add(wrist, mul(unit(tip, side),
                                               math.dist(a["wrist"], a["hand"])))}
            inward = mul(frame["left"], -1 if side == "left" else 1)
            flexion[side] = inward_flexion(arm, inward, f"{start['pose_id']}→{end['pose_id']} {index} {side}")
            arms[side] = arm
        result.append({"frame": index + 1, "arms": arms, "inward_flexion": flexion,
                       "from": start["pose_id"], "to": end["pose_id"]})
    return result


def route_arm_positions(start: str, end: str,
                        connecting_edges: dict[tuple[str, str], list[dict]]) -> list[str]:
    """Plan every catalog pair through only generated, reversible edge actions."""
    adjacency = {}
    for a, b in connecting_edges:
        adjacency.setdefault(a, set()).add(b)
        adjacency.setdefault(b, set()).add(a)
    require(start in adjacency and end in adjacency, "route", "unknown catalog position")
    paths = deque([[start]])
    visited = {start}
    while paths:
        path = paths.popleft()
        if path[-1] == end:
            return path
        for neighbor in sorted(adjacency[path[-1]] - visited):
            visited.add(neighbor)
            paths.append(path + [neighbor])
    require(False, "route", "catalog graph has an unreachable position")
