"""Phase 10.11.2 asymmetric crossed-reverence stance semantics."""

from __future__ import annotations

import copy
import itertools


LOWER_JOINT_CLASSES={
    "thigh":"hip_ball",
    "shin":"knee_hinge",
    "foot":"ankle_2dof",
    "toes":"mtp_hinge",
}


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.11.2":
        raise ValueError("10.11.2 phase mismatch.")
    if contract.get("contract_id") != "opening_reverence_crossed_stance_v1":
        raise ValueError("10.11.2 contract id mismatch.")

    sides=contract["side_assignment"]
    if sides["support_side"] != "left" or sides["gesture_side"] != "right":
        raise ValueError("10.11.2 side assignment changed.")

    lower=contract["lower_body"]
    if lower["source_authority"] != "NEW_CANONICAL_ASYMMETRIC_REVERENCE_STATE":
        raise ValueError("Crossed stance canonical authority changed.")
    if lower["support_contact"] != "FULL_FOOT":
        raise ValueError("Support foot must remain full-foot.")
    if lower["gesture_contact"] != "FOREFOOT_OR_TOE_TOUCH":
        raise ValueError("Gesture contact semantics changed.")
    if float(lower["pelvis_support_shift_hip_width_fraction"]) > 0.15:
        raise ValueError("Pelvis support shift is too large.")

    search=lower["gesture_search"]
    if len(search["hip_flexion_extension_deg"]) > 4:
        raise ValueError("Gesture extension search grew too broad.")
    if len(search["hip_abduction_adduction_deg"]) > 4:
        raise ValueError("Gesture adduction search grew too broad.")
    if len(search["ankle_plantar_dorsiflexion_deg"]) > 4:
        raise ValueError("Gesture ankle search grew too broad.")

    upper=contract["upper_body"]
    if upper["arm_pose"] != "bras_bas":
        raise ValueError("10.11.2 arm source must remain bras_bas.")
    if upper["arm_authority"] != "PHASE_10_6_ACCEPTED_REALIZATION":
        raise ValueError("10.11.2 arm authority changed.")
    if upper["canonical_axis"] != "X":
        raise ValueError("Reverence bow must remain canonical-X.")

    geometry=contract["geometry_targets"]
    if float(geometry["gesture_cross_min_foot_fraction"]) < 0.05:
        raise ValueError("Gesture cross gate is too weak.")
    if float(geometry["gesture_back_min_foot_fraction"]) < 0.08:
        raise ValueError("Gesture back gate is too weak.")
    if float(geometry["gesture_heel_lift_min_foot_fraction"]) < 0.03:
        raise ValueError("Gesture heel-lift gate is too weak.")
    if float(geometry["support_full_foot_error_max_foot_fraction"]) > 0.05:
        raise ValueError("Support contact gate is too loose.")

    validation=contract["validation"]
    for key in (
        "all_joint_values_within_preferred_envelope",
        "support_full_foot_contact_required",
        "gesture_forefoot_near_floor_required",
        "gesture_heel_lift_required",
        "gesture_cross_and_back_required",
        "lower_body_asymmetry_required",
        "hand_centerline_crossing_forbidden",
        "no_permanent_constraints",
        "imported_action_must_be_cleared",
    ):
        if not validation.get(key,False):
            raise ValueError(f"10.11.2 validation gate changed: {key}.")

    policy=contract["policy"]
    for key in (
        "static_pose_only","animation_forbidden","world_turn_forbidden",
        "run_handoff_forbidden","music_sync_forbidden",
        "gameplay_changes_forbidden","glb_export_forbidden",
    ):
        if not policy.get(key,False):
            raise ValueError(f"10.11.2 scope gate changed: {key}.")


def candidate_parameter_sets(contract: dict):
    validate_contract(contract)
    search=contract["lower_body"]["gesture_search"]
    for extension,adduction,plantar in itertools.product(
        search["hip_flexion_extension_deg"],
        search["hip_abduction_adduction_deg"],
        search["ankle_plantar_dorsiflexion_deg"],
    ):
        yield {
            "gesture_hip_flexion_extension_deg":float(extension),
            "gesture_hip_abduction_adduction_deg":float(adduction),
            "gesture_ankle_plantar_dorsiflexion_deg":float(plantar),
        }


def build_state(contract: dict, parameters: dict) -> dict:
    validate_contract(contract)
    lower=contract["lower_body"]
    support=copy.deepcopy(lower["support"])
    gesture=lower["gesture_fixed"]

    joint_dofs={
        "left_thigh":copy.deepcopy(support["thigh"]),
        "left_shin":copy.deepcopy(support["shin"]),
        "left_foot":copy.deepcopy(support["foot"]),
        "left_toes":copy.deepcopy(support["toes"]),
        "right_thigh":{
            "flexion_extension":float(
                parameters["gesture_hip_flexion_extension_deg"]
            ),
            "abduction_adduction":float(
                parameters["gesture_hip_abduction_adduction_deg"]
            ),
            "internal_external_rotation":float(
                gesture["internal_external_rotation"]
            ),
        },
        "right_shin":{
            "flexion_extension":float(
                gesture["knee_flexion_extension"]
            ),
        },
        "right_foot":{
            "plantar_dorsiflexion":float(
                parameters["gesture_ankle_plantar_dorsiflexion_deg"]
            ),
            "inversion_eversion":float(
                gesture["inversion_eversion"]
            ),
        },
        "right_toes":{
            "toe_flexion_extension":float(
                gesture["toe_flexion_extension"]
            ),
        },
    }

    return {
        "pose":"reverence_crossed_stance",
        "contacts":{"left":"FULL_FOOT","right":"FOREFOOT_OR_TOE_TOUCH"},
        "turnout":{
            "left":{
                "knee_external_rotation_deg":float(
                    support["knee_external_rotation_deg"]
                )
            },
            "right":{
                "knee_external_rotation_deg":float(
                    gesture["knee_external_rotation_deg"]
                )
            },
        },
        "joint_dofs":joint_dofs,
        "scalars":{},
        "com":{"support_side":"left"},
    }


def preferred_envelope_violations(state: dict, constraints: dict) -> list[str]:
    violations=[]
    bones=state["joint_dofs"]
    for canonical_name,dofs in bones.items():
        suffix=canonical_name.split("_",1)[1]
        joint_class=LOWER_JOINT_CLASSES[suffix]
        limits=constraints["joint_limits"][joint_class]["dofs"]
        for dof,value in dofs.items():
            preferred=limits[dof]["preferred"]
            numeric=float(value)
            if numeric < float(preferred["min"]) or numeric > float(preferred["max"]):
                violations.append(
                    f"{canonical_name}.{dof}={numeric} outside "
                    f"[{preferred['min']},{preferred['max']}]"
                )
    return violations
