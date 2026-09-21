"""Phase 10.7.1 deterministic foundation-motion timing helpers.

This module contains no rig or Blender authority. It only defines the
time law and the proportional semantic-envelope diagnostic used by the
single humanoid Blender prototype.
"""

from __future__ import annotations

import math


ROLE_ORDER = ("shoulder", "elbow", "wrist", "fingers")
ROLE_TO_INTENT = {
    "shoulder": ("upper_arm", "shoulder_ball"),
    "elbow": ("forearm", "elbow_twist"),
    "wrist": ("hand", "wrist_2dof"),
}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def minimum_jerk(value: float) -> float:
    t = clamp01(value)
    return t * t * t * (10.0 + t * (-15.0 + 6.0 * t))


def windowed_progress(normalized_time: float, window: dict) -> float:
    start = float(window["start"])
    end = float(window["end"])
    if not 0.0 <= start < end <= 1.0:
        raise ValueError(f"Invalid motion window: {window}")
    local = (clamp01(normalized_time) - start) / (end - start)
    return minimum_jerk(local)


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.7.1":
        raise ValueError("Foundation motion contract phase mismatch.")
    transition = contract["transition"]
    if transition["start_pose"] != "bras_bas":
        raise ValueError("10.7.1 must start at bras_bas.")
    if transition["end_pose"] != "en_avant":
        raise ValueError("10.7.1 must end at en_avant.")
    duration = float(transition["duration_seconds"])
    if not 1.5 <= duration <= 2.5:
        raise ValueError("10.7.1 duration must stay in the 1.5-2.5 s proof window.")
    if int(transition["fps"]) <= 0:
        raise ValueError("FPS must be positive.")
    if contract["curve"]["type"] != "MINIMUM_JERK":
        raise ValueError("10.7.1 requires deterministic minimum-jerk timing.")
    if not contract["curve"].get("overshoot_forbidden", False):
        raise ValueError("Motion overshoot must remain forbidden.")

    projection = contract["validation"]["centerline_clearance_projection"]
    if not projection.get("enabled", False):
        raise ValueError("Intermediate centerline clearance projection must remain enabled.")
    guard = float(projection["intermediate_guard_side_offset"])
    if not 0.0 <= guard <= 0.005:
        raise ValueError("Intermediate hand-clearance guard must stay within [0, 0.005].")
    maximum = float(projection["maximum_shoulder_correction_deg"])
    if not 0.0 < maximum <= 5.0:
        raise ValueError("Centerline shoulder correction must stay within (0, 5] degrees.")
    iterations = int(projection["bisection_iterations"])
    if not 8 <= iterations <= 32:
        raise ValueError("Centerline projection bisection iterations must stay within [8, 32].")
    axes = list(projection["candidate_axes"])
    if not axes or any(axis not in ("front", "up") for axis in axes):
        raise ValueError("Centerline projection may use only declared front/up body axes.")

    windows = contract["joint_windows"]
    starts = [float(windows[role]["start"]) for role in ROLE_ORDER]
    ends = [float(windows[role]["end"]) for role in ROLE_ORDER]
    widths = [
        float(windows[role]["end"]) - float(windows[role]["start"])
        for role in ROLE_ORDER
    ]
    if starts != sorted(starts):
        raise ValueError("Motion must initiate proximal-to-distal.")
    if ends != sorted(ends):
        raise ValueError("Motion must settle proximal-to-distal.")
    if any(widths[index] < widths[index + 1] - 1e-12 for index in range(3)):
        raise ValueError("Distal temporal window may not exceed its proximal parent.")
    for role in ROLE_ORDER:
        windowed_progress(0.0, windows[role])
        windowed_progress(1.0, windows[role])

    maximum_lag = float(
        contract["validation"]["maximum_adjacent_role_progress_lag"]
    )
    if not 0.0 < maximum_lag <= 0.05:
        raise ValueError(
            "Maximum adjacent role progress lag must stay within (0, 0.05]."
        )
    for index in range(1001):
        t = index / 1000.0
        progress = {
            role: windowed_progress(t, windows[role])
            for role in ROLE_ORDER
        }
        for proximal, distal in zip(ROLE_ORDER, ROLE_ORDER[1:]):
            lag = progress[proximal] - progress[distal]
            if lag < -1e-12:
                raise ValueError(
                    f"Distal role {distal} may not lead proximal role "
                    f"{proximal}; t={t}, lag={lag}."
                )
            if lag > maximum_lag + 1e-12:
                raise ValueError(
                    f"Adjacent role progress lag exceeds contract; "
                    f"{proximal}->{distal}, t={t}, lag={lag}, "
                    f"maximum={maximum_lag}."
                )


def frame_end(contract: dict) -> int:
    validate_contract(contract)
    transition = contract["transition"]
    count = round(
        float(transition["duration_seconds"]) * int(transition["fps"])
    )
    return int(transition["frame_start"]) + int(count)


def normalized_time(frame: int, contract: dict) -> float:
    start = int(contract["transition"]["frame_start"])
    end = frame_end(contract)
    if end <= start:
        raise ValueError("Degenerate motion frame range.")
    return clamp01((int(frame) - start) / float(end - start))


def progress_trace(frame: int, contract: dict) -> dict[str, float]:
    t = normalized_time(frame, contract)
    windows = contract["joint_windows"]
    return {
        role: windowed_progress(t, windows[role])
        for role in ROLE_ORDER
    }


def _preferred_range(constraints: dict, joint_class: str, dof: str) -> tuple[float, float]:
    preferred = constraints["joint_limits"][joint_class]["dofs"][dof]["preferred"]
    return float(preferred["min"]), float(preferred["max"])


def semantic_dof_proxy(
    normalized_t: float,
    contract: dict,
    intent_spec: dict,
    constraints: dict,
) -> dict:
    """Return a no-overshoot semantic DOF diagnostic.

    The proxy is deliberately not a pose solver. It interpolates only the
    already-declared endpoint semantic DOFs with the same joint-role timing
    used by the quaternion motion, then checks the Phase 10.6.3 preferred
    envelope. Actual wrist axial continuity is validated on the realized rig
    by the Blender gate.
    """

    start_name = contract["transition"]["start_pose"]
    end_name = contract["transition"]["end_pose"]
    start_pose = intent_spec["poses"][start_name]["joint_dofs"]
    end_pose = intent_spec["poses"][end_name]["joint_dofs"]
    result = {"status": "PASS", "roles": {}}

    for role, (intent_key, joint_class) in ROLE_TO_INTENT.items():
        p = windowed_progress(normalized_t, contract["joint_windows"][role])
        start_dofs = start_pose[intent_key]
        end_dofs = end_pose[intent_key]
        dof_result = {}
        for dof in sorted(set(start_dofs) | set(end_dofs)):
            a = float(start_dofs[dof])
            b = float(end_dofs[dof])
            value = a + (b - a) * p
            minimum, maximum = _preferred_range(constraints, joint_class, dof)
            passed = minimum - 1e-9 <= value <= maximum + 1e-9
            dof_result[dof] = {
                "value": value,
                "preferred_min": minimum,
                "preferred_max": maximum,
                "status": "PASS" if passed else "FAIL",
            }
            if not passed:
                result["status"] = "FAIL"
        result["roles"][role] = {
            "progress": p,
            "joint_class": joint_class,
            "dofs": dof_result,
        }
    return result
