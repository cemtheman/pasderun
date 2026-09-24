"""Signed elbow-flexion guard for body-relative arm pose candidates.

The guard follows the upper arm, so a shoulder rotation changes the measured
bend direction. Body-inward is an authored bend-side cue; a calibrated local
hinge axis and physiological range remain separate, unresolved rig evidence.
"""

from __future__ import annotations

import math

from schema_validation import require
from static_pose import dot, mul, sub


def inward_flexion(arm: dict, inward_axis: list[float], where: str) -> dict:
    """Reject an elbow bending to the outward side of the upper-arm axis."""
    upper = sub(arm["elbow"], arm["shoulder"])
    lower = sub(arm["wrist"], arm["elbow"])
    upper_length, lower_length = math.sqrt(dot(upper, upper)), math.sqrt(dot(lower, lower))
    require(upper_length > 1e-8 and lower_length > 1e-8, where, "degenerate arm segment")
    upper_direction = mul(upper, 1 / upper_length)
    perpendicular = sub(lower, mul(upper_direction, dot(lower, upper_direction)))
    inward = sub(inward_axis, mul(upper_direction, dot(inward_axis, upper_direction)))
    inward_length = math.sqrt(dot(inward, inward))
    bend_length = math.sqrt(dot(perpendicular, perpendicular))
    require(inward_length > 1e-6, where, "inward direction parallel to upper arm")
    require(bend_length > lower_length * 1e-4, where, "elbow is singularly straight")
    signed = dot(perpendicular, inward) / (bend_length * inward_length)
    require(signed > 1e-5, where, "elbow flexes outward rather than inward")
    return {"signed_inward_alignment": round(signed, 8),
            "bend_from_straight_deg": round(math.degrees(math.atan2(
                bend_length, dot(lower, upper_direction))), 6)}
