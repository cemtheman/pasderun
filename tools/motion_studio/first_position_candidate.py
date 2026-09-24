"""Guide-derived first arm position candidate, separate from Phase 10 en avant."""

from __future__ import annotations

import math

from elbow_flexion import inward_flexion
from schema_validation import require
from static_pose import add, dot, mul, solve_two_link, sub


def guide_first_position(preparatory: dict, en_avant_reference: dict,
                         anatomical_frame: dict) -> dict:
    """Place the first-position wrist between known low and high wrist levels.

    The mid-height is a testable navel-region hypothesis, NOT a measured
    navel landmark. The reviewed preparatory pose and original Phase 10 data
    provide the two bounds. The wrist's lateral separation remains unchanged.
    """
    require(preparatory["pose_id"] == "bras_bas" and
            en_avant_reference["pose_id"] == "en_avant", "first", "wrong source poses")
    up, front = anatomical_frame["up"], anatomical_frame["front"]
    left_axis = anatomical_frame["left"]
    result = {}
    for side in ("left", "right"):
        low = preparatory["arms"][side]
        high = en_avant_reference["arms"][side]
        require(math.dist(low["shoulder"], high["shoulder"]) < 1e-7,
                side, "reference shoulders differ")
        upper = math.dist(high["shoulder"], high["elbow"])
        forearm = math.dist(high["elbow"], high["wrist"])
        require(abs(upper - math.dist(low["shoulder"], low["elbow"])) < 1e-5 and
                abs(forearm - math.dist(low["elbow"], low["wrist"])) < 1e-5,
                side, "source arm lengths differ")
        low_up, high_up = dot(low["wrist"], up), dot(high["wrist"], up)
        require(high_up > low_up + 1e-6, side, "first position has no vertical bounds")
        # Midpoint of the two observed wrist levels. Front moves halfway from
        # preparatory to the existing high Phase 10 target; lateral stays at
        # the already cleared en avant wrist location.
        wrist = add(high["wrist"], add(
            mul(up, (low_up - high_up) / 2),
            mul(front, (dot(low["wrist"], front) - dot(high["wrist"], front)) / 2)))
        outward = left_axis if side == "left" else mul(left_axis, -1)
        solved = solve_two_link(high["shoulder"], high["elbow"], high["wrist"],
                                wrist, outward, side)
        hand = add(wrist, sub(high["hand"], high["wrist"]))
        arm = {**high, "elbow": solved["elbow"], "wrist": wrist, "hand": hand}
        inward_flexion(arm, mul(outward, -1), side)
        require(low_up < dot(wrist, up) < high_up, side, "wrist outside first-position level")
        result[side] = arm
    return {"pose_id": "first_position_candidate", "arms": result}
