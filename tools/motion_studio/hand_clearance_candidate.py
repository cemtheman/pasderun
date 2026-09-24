"""Geometric arm candidate from measured hand-silhouette overlap.

Wrist moves outward in the declared body frame; elbow is re-solved from
measured shoulder/elbow/wrist lengths and the original elbow bend direction.
"""

from __future__ import annotations

from schema_validation import require
from static_pose import add, mul, sub, solve_two_link


def shifted_solution(solution: dict, frame: dict, shift: float,
                     elbow_pole: str = "reference") -> dict:
    require(solution["pose_id"] in ("bras_bas", "en_avant"), "clearance", "only inward-hand reference poses")
    require(shift >= 0, "clearance", "negative outward shift")
    require(elbow_pole in ("reference", "body_outward"), "clearance", "unknown elbow pole")
    require(elbow_pole == "reference" or solution["pose_id"] == "en_avant",
            "clearance", "outward elbow pole applies only to en avant")
    arms = {}
    for side, original in solution["arms"].items():
        sign = 1 if side == "left" else -1
        goal = add(original["wrist"], mul(frame["left"], sign * shift))
        pole = (sub(original["elbow"], original["shoulder"])
                if elbow_pole == "reference" else mul(frame["left"], sign))
        solved = solve_two_link(original["shoulder"], original["elbow"],
                                original["wrist"], goal, pole, side)
        arms[side] = {**original, "elbow": solved["elbow"], "wrist": goal,
                      "hand": add(goal, sub(original["hand"], original["wrist"]))}
    return {"pose_id": solution["pose_id"], "arms": arms}
