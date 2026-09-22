"""Phase 10.8.1 lower-body foundation-motion timing helpers.

No Blender or rig authority lives here. The module defines the deterministic
minimum-jerk time law and a semantic preferred-envelope proxy for fifth -> plie.
"""

from __future__ import annotations


LOWER_DOF_TO_CONSTRAINT = {
    "thigh": "hip_ball",
    "shin": "knee_hinge",
    "foot": "ankle_2dof",
    "toes": "mtp_hinge",
}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def minimum_jerk(value: float) -> float:
    t = clamp01(value)
    return t * t * t * (10.0 + t * (-15.0 + 6.0 * t))


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.8.1":
        raise ValueError("Lower-body motion contract phase mismatch.")

    transition = contract["transition"]
    if transition["start_pose"] != "fifth":
        raise ValueError("10.8.1 must start at fifth.")
    if transition["end_pose"] != "plie":
        raise ValueError("10.8.1 must end at plie.")
    if not 1.5 <= float(transition["duration_seconds"]) <= 2.5:
        raise ValueError("10.8.1 duration must stay in the 1.5-2.5 s proof window.")
    if int(transition["fps"]) <= 0:
        raise ValueError("FPS must be positive.")

    curve = contract["curve"]
    if curve["type"] != "MINIMUM_JERK":
        raise ValueError("10.8.1 requires deterministic minimum-jerk timing.")
    if not curve.get("overshoot_forbidden", False):
        raise ValueError("Motion overshoot must remain forbidden.")

    interpolation = contract["interpolation"]
    if interpolation["rotation"] != "QUATERNION_SHORTEST_ARC_SLERP":
        raise ValueError("Lower-body rotations must use shortest-arc quaternion slerp.")
    if interpolation["progress"] != "SYNCHRONOUS_MINIMUM_JERK":
        raise ValueError("10.8.1 uses one synchronous minimum-jerk progress.")
    if (
        interpolation["pelvis_translation"]
        != "PER_FRAME_DEFORMED_MESH_FULL_FOOT_CONTACT_SOLVE"
    ):
        raise ValueError("Pelvis translation must remain mesh-contact solved.")
    if interpolation["non_root_translation"] != "LOCK_TO_START":
        raise ValueError("Non-root moving translations must stay locked.")
    if interpolation["scale"] != "LOCK_TO_START":
        raise ValueError("Moving scales must stay locked.")

    validation = contract["validation"]
    if float(validation["accepted_endpoint_locked_noise_max"]) > 1e-6:
        raise ValueError("Accepted endpoint locked-noise ceiling may not exceed 1e-6.")
    if float(validation["locked_local_matrix_error_max"]) > 1e-7:
        raise ValueError("Locked motion drift ceiling may not exceed 1e-7.")
    if float(validation["moving_non_root_translation_error_max"]) > 1e-6:
        raise ValueError("Non-root moving translation ceiling may not exceed 1e-6.")
    if float(validation["moving_scale_error_max"]) > 1e-6:
        raise ValueError("Moving scale ceiling may not exceed 1e-6.")
    if float(validation["root_horizontal_translation_max"]) > 1e-5:
        raise ValueError("Root horizontal drift ceiling is too loose.")
    if float(validation["root_descent_monotonic_epsilon"]) > 1e-4:
        raise ValueError("Root descent monotonic epsilon is too loose.")
    if not validation.get("full_foot_contact_required_every_frame", False):
        raise ValueError("Full-foot contact must be required every frame.")
    if not validation.get("sample_every_frame", False):
        raise ValueError("10.8.1 must sample every frame.")

    drivers = set(validation["semantic_driver_canonical_bones"])
    required = set(validation["required_motion_canonical_bones"])
    if not required <= drivers:
        raise ValueError(
            "Required moving bones must be a subset of semantic drivers."
        )
    if "pelvis" not in required:
        raise ValueError("Pelvis must participate in fifth -> plie motion.")
    for name in ("spine_lower", "spine_mid", "chest"):
        if name not in required:
            raise ValueError(
                "Plié trunk-tilt drivers must remain required motion bones."
            )
    if validation.get("trunk_hierarchy_propagation_root") != "chest":
        raise ValueError(
            "Accepted trunk hierarchy propagation must remain rooted at chest."
        )
    authority = contract["authority"]
    if not authority.get(
        "independent_upper_body_authoring_forbidden",
        False,
    ):
        raise ValueError("Independent upper-body authoring must stay forbidden.")
    if (
        authority.get("trunk_tilt_authority")
        != "PHASE_10_6_TRUNK_TILT_SCALAR_ORIENTATION_ROUTE"
    ):
        raise ValueError("Plié trunk-tilt authority changed.")
    if not authority.get(
        "hierarchy_propagated_endpoint_motion_required",
        False,
    ):
        raise ValueError(
            "Accepted hierarchy-propagated endpoint motion must be retained."
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


def progress(frame: int, contract: dict) -> float:
    return minimum_jerk(normalized_time(frame, contract))


def interpolate_bounded_scalar(
    start_value: float,
    end_value: float,
    progress_value: float,
) -> float:
    p = clamp01(progress_value)
    start = float(start_value)
    end = float(end_value)
    value = start + (end - start) * p
    minimum = min(start, end)
    maximum = max(start, end)
    if not minimum - 1e-12 <= value <= maximum + 1e-12:
        raise ValueError(
            f"Bounded interpolation overshoot: {value} outside "
            f"[{minimum}, {maximum}]."
        )
    return value


def _preferred_range(
    constraints: dict,
    joint_class: str,
    dof: str,
) -> tuple[float, float]:
    preferred = constraints["joint_limits"][joint_class]["dofs"][dof]["preferred"]
    return float(preferred["min"]), float(preferred["max"])


def semantic_dof_proxy(
    normalized_t: float,
    contract: dict,
    intent_spec: dict,
    constraints: dict,
) -> dict:
    start_name = contract["transition"]["start_pose"]
    end_name = contract["transition"]["end_pose"]
    start_pose = intent_spec["poses"][start_name]["joint_dofs"]
    end_pose = intent_spec["poses"][end_name]["joint_dofs"]
    p = minimum_jerk(normalized_t)

    start_trunk = float(
        intent_spec["poses"][start_name].get("trunk_tilt_deg", 0.0)
    )
    end_trunk = float(
        intent_spec["poses"][end_name].get("trunk_tilt_deg", 0.0)
    )
    trunk_tilt = interpolate_bounded_scalar(
        start_trunk,
        end_trunk,
        p,
    )

    result = {
        "status": "PASS",
        "progress": p,
        "trunk_tilt_deg": trunk_tilt,
        "joints": {},
    }
    for intent_key, joint_class in LOWER_DOF_TO_CONSTRAINT.items():
        start_dofs = start_pose[intent_key]
        end_dofs = end_pose[intent_key]
        dof_result = {}
        for dof in sorted(set(start_dofs) | set(end_dofs)):
            value = interpolate_bounded_scalar(
                float(start_dofs[dof]),
                float(end_dofs[dof]),
                p,
            )
            minimum, maximum = _preferred_range(
                constraints,
                joint_class,
                dof,
            )
            passed = minimum - 1e-9 <= value <= maximum + 1e-9
            dof_result[dof] = {
                "value": value,
                "preferred_min": minimum,
                "preferred_max": maximum,
                "status": "PASS" if passed else "FAIL",
            }
            if not passed:
                result["status"] = "FAIL"
        result["joints"][intent_key] = {
            "joint_class": joint_class,
            "dofs": dof_result,
        }
    return result
