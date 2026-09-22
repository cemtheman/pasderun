"""Phase 10.8.2 plie -> releve deterministic timing helpers."""

from __future__ import annotations

from lower_body_foundation_motion import (
    LOWER_DOF_TO_CONSTRAINT,
    clamp01,
    minimum_jerk,
    interpolate_bounded_scalar,
    _preferred_range,
)


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.8.2":
        raise ValueError("10.8.2 contract phase mismatch.")
    transition = contract["transition"]
    if transition["start_pose"] != "plie":
        raise ValueError("10.8.2 must start at plie.")
    if transition["end_pose"] != "releve":
        raise ValueError("10.8.2 must end at releve.")
    if not 1.5 <= float(transition["duration_seconds"]) <= 2.5:
        raise ValueError("10.8.2 duration must stay in the 1.5-2.5 s proof window.")
    if int(transition["fps"]) <= 0:
        raise ValueError("FPS must be positive.")

    curve = contract["curve"]
    if curve["type"] != "MINIMUM_JERK" or not curve.get("overshoot_forbidden"):
        raise ValueError("10.8.2 requires bounded minimum-jerk timing.")

    interpolation = contract["interpolation"]
    if interpolation["rotation"] != "QUATERNION_SHORTEST_ARC_SLERP":
        raise ValueError("Rotations must use shortest-arc quaternion slerp.")
    if interpolation["progress"] != "SYNCHRONOUS_MINIMUM_JERK":
        raise ValueError("10.8.2 uses one synchronous progress law.")
    if (
        interpolation["pelvis_translation"]
        != "PER_FRAME_DEFORMED_MESH_FOREFOOT_CONTACT_SOLVE"
    ):
        raise ValueError("Pelvis translation must use per-frame forefoot contact.")
    if interpolation["start_contact_mode"] != "SOLVE_FULL_FOOT_CONTACT":
        raise ValueError("Plié start must retain full-foot contact.")
    if interpolation["intermediate_contact_mode"] != "SOLVE_FOREFOOT_CONTACT":
        raise ValueError("Intermediate relevé motion must use forefoot contact.")
    if interpolation["end_contact_mode"] != "SOLVE_FOREFOOT_CONTACT":
        raise ValueError("Relevé endpoint must retain forefoot contact.")
    if interpolation["non_root_translation"] != "LOCK_TO_START":
        raise ValueError("Non-root translations must stay locked.")
    if interpolation["scale"] != "LOCK_TO_START":
        raise ValueError("Scale must stay locked.")

    authority = contract["authority"]
    if not authority.get("intermediate_plantar_toe_search_forbidden", False):
        raise ValueError("Intermediate plantar/toe search must stay forbidden.")
    if not authority.get("independent_upper_body_authoring_forbidden", False):
        raise ValueError("Independent upper-body authoring must stay forbidden.")
    if not authority.get("hierarchy_propagated_endpoint_motion_required", False):
        raise ValueError("Accepted hierarchy propagation must remain authoritative.")

    validation = contract["validation"]
    if float(validation["accepted_endpoint_locked_noise_max"]) > 1e-6:
        raise ValueError("Locked endpoint noise ceiling may not exceed 1e-6.")
    if float(validation["locked_local_matrix_error_max"]) > 1e-7:
        raise ValueError("Locked motion drift ceiling may not exceed 1e-7.")
    if float(validation["moving_non_root_translation_error_max"]) > 1e-6:
        raise ValueError("Non-root translation ceiling may not exceed 1e-6.")
    if float(validation["moving_scale_error_max"]) > 1e-6:
        raise ValueError("Motion scale ceiling may not exceed 1e-6.")
    if float(validation["accepted_endpoint_decomposition_noise_max"]) > 1e-5:
        raise ValueError(
            "Endpoint decomposition noise may not exceed the accepted "
            "Phase 10.6 local-matrix precision ceiling of 1e-5."
        )
    if (
        validation.get("accepted_endpoint_decomposition_noise_authority")
        != "PHASE_10_6_STATIC_LOCAL_ROTATION_MATRIX_ERROR_MAX"
    ):
        raise ValueError("Endpoint decomposition precision authority changed.")
    if (
        interpolation.get("rotation_source")
        != "NORMALIZED_ENDPOINT_LOCAL_3X3_BASIS"
    ):
        raise ValueError(
            "10.8.2 rotations must come from normalized endpoint bases."
        )
    if float(validation["root_horizontal_translation_max"]) > 1e-5:
        raise ValueError("Root horizontal drift ceiling is too loose.")
    if float(validation["root_rise_monotonic_epsilon"]) > 1e-4:
        raise ValueError("Root-rise epsilon is too loose.")
    if float(validation["heel_lift_monotonic_epsilon"]) > 1e-4:
        raise ValueError("Heel-lift epsilon is too loose.")
    if not validation.get("sample_every_frame", False):
        raise ValueError("10.8.2 must sample every frame.")
    if not validation.get("start_full_foot_contact_required", False):
        raise ValueError("Plié start full-foot contact must remain required.")
    if not validation.get("intermediate_forefoot_contact_required", False):
        raise ValueError("Intermediate forefoot contact must remain required.")
    if not validation.get("end_forefoot_contact_required", False):
        raise ValueError("Relevé endpoint forefoot contact must remain required.")

    drivers=set(validation["semantic_driver_canonical_bones"])
    required=set(validation["required_motion_canonical_bones"])
    if not required <= drivers:
        raise ValueError("Required motion bones must be semantic drivers.")
    for name in ("pelvis","left_foot","left_toes","right_foot","right_toes",
                 "spine_lower","spine_mid","chest"):
        if name not in required:
            raise ValueError(f"Required 10.8.2 driver missing: {name}.")
    if validation.get("trunk_hierarchy_propagation_root") != "chest":
        raise ValueError("Trunk hierarchy root must remain chest.")


def frame_end(contract: dict) -> int:
    validate_contract(contract)
    t=contract["transition"]
    return int(t["frame_start"]) + round(float(t["duration_seconds"])*int(t["fps"]))


def normalized_time(frame: int, contract: dict) -> float:
    start=int(contract["transition"]["frame_start"])
    end=frame_end(contract)
    if end <= start:
        raise ValueError("Degenerate frame range.")
    return clamp01((int(frame)-start)/float(end-start))


def progress(frame: int, contract: dict) -> float:
    return minimum_jerk(normalized_time(frame, contract))


def semantic_dof_proxy(
    normalized_t: float,
    contract: dict,
    intent_spec: dict,
    constraints: dict,
) -> dict:
    start_name=contract["transition"]["start_pose"]
    end_name=contract["transition"]["end_pose"]
    start_pose=intent_spec["poses"][start_name]["joint_dofs"]
    end_pose=intent_spec["poses"][end_name]["joint_dofs"]
    p=minimum_jerk(normalized_t)

    start_trunk=float(intent_spec["poses"][start_name].get("trunk_tilt_deg",0.0))
    end_trunk=float(intent_spec["poses"][end_name].get("trunk_tilt_deg",0.0))
    trunk_tilt=interpolate_bounded_scalar(start_trunk,end_trunk,p)

    result={"status":"PASS","progress":p,"trunk_tilt_deg":trunk_tilt,"joints":{}}
    for intent_key,joint_class in LOWER_DOF_TO_CONSTRAINT.items():
        start_dofs=start_pose[intent_key]
        end_dofs=end_pose[intent_key]
        dof_result={}
        for dof in sorted(set(start_dofs)|set(end_dofs)):
            value=interpolate_bounded_scalar(
                float(start_dofs[dof]),float(end_dofs[dof]),p
            )
            minimum,maximum=_preferred_range(constraints,joint_class,dof)
            passed=minimum-1e-9 <= value <= maximum+1e-9
            dof_result[dof]={
                "value":value,"preferred_min":minimum,"preferred_max":maximum,
                "status":"PASS" if passed else "FAIL",
            }
            if not passed:
                result["status"]="FAIL"
        result["joints"][intent_key]={"joint_class":joint_class,"dofs":dof_result}
    return result
