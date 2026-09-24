"""Sample a geometry-only path through reviewed preparatory, en avant and second candidates."""

from __future__ import annotations

import math

from elbow_flexion import inward_flexion
from schema_validation import require
from static_pose import add, length, mul, solve_two_link, sub


def _lerp(a, b, t):
    return add(mul(a, 1 - t), mul(b, t))


def sample_port_de_bras(poses: dict, frame: dict, frames_per_leg: int = 24) -> list[dict]:
    """Every sample re-solves the arm segments from measured endpoint lengths.

    Sample indices are a review grid; they do not encode choreography timing.
    """
    order = ("bras_bas", "en_avant", "second")
    require(set(poses) == set(order), "path", "requires three candidate poses")
    require(isinstance(frames_per_leg, int) and frames_per_leg >= 2, "path", "invalid sampling grid")
    result = []
    for leg, (start_name, end_name) in enumerate(zip(order, order[1:])):
        start, end = poses[start_name], poses[end_name]
        for index in range(frames_per_leg + 1):
            if leg and index == 0:
                continue
            t = index / frames_per_leg
            eased = t * t * (3 - 2 * t)
            arms, flexion = {}, {}
            require(set(start["arms"]) == set(end["arms"]) == {"left", "right"},
                    "path", "arm sides differ")
            for side in ("left", "right"):
                a, b = start["arms"][side], end["arms"][side]
                shoulder = a["shoulder"]
                require(math.dist(shoulder, b["shoulder"]) < 1e-7, side,
                        "shoulder changes between reference poses")
                for joint_a, joint_b in (("shoulder", "elbow"), ("elbow", "wrist"),
                                          ("wrist", "hand")):
                    require(abs(math.dist(a[joint_a], a[joint_b]) -
                                math.dist(b[joint_a], b[joint_b])) < 1e-5,
                            side, "segment length differs between candidates")
                if index == 0:
                    arm = a.copy()
                elif index == frames_per_leg:
                    arm = b.copy()
                else:
                    wrist = _lerp(a["wrist"], b["wrist"], eased)
                    bend_pole = _lerp(sub(a["elbow"], shoulder),
                                      sub(b["elbow"], shoulder), eased)
                    solved = solve_two_link(shoulder, a["elbow"], a["wrist"],
                                            wrist, bend_pole, side)
                    direction = _lerp(sub(a["hand"], a["wrist"]),
                                      sub(b["hand"], b["wrist"]), eased)
                    require(length(direction) > 1e-8, side, "hand direction vanished")
                    hand = add(wrist, mul(direction,
                                         length(sub(a["hand"], a["wrist"])) / length(direction)))
                    arm = {**a, "elbow": solved["elbow"], "wrist": wrist, "hand": hand}
                inward = mul(frame["left"], -1 if side == "left" else 1)
                flexion[side] = inward_flexion(arm, inward, f"frame {leg * frames_per_leg + index + 1} {side}")
                arms[side] = arm
            result.append({"frame": leg * frames_per_leg + index + 1,
                           "from": start_name, "to": end_name,
                           "leg_fraction": round(t, 8), "arms": arms,
                           "inward_flexion": flexion})
    return result
