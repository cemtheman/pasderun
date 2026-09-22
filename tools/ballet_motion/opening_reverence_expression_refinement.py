"""Phase 10.11.3 reverence upper-body expression refinement."""

from __future__ import annotations

import itertools


ARM_JOINT_CLASSES={
    "upper_arm":"shoulder_ball",
    "forearm":"elbow_twist",
    "hand":"wrist_2dof",
}


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.11.3":
        raise ValueError("10.11.3 phase mismatch.")
    if contract.get("contract_id") != (
        "opening_reverence_expression_refinement_v1"
    ):
        raise ValueError("10.11.3 contract id mismatch.")

    lower=contract["lower_body_authority"]
    if lower["source_phase"] != "10.11.2":
        raise ValueError("Frozen lower source phase changed.")
    if lower["source_contract_id"] != "opening_reverence_crossed_stance_v1":
        raise ValueError("Frozen lower source contract changed.")
    if lower["frozen_selected_parameters"] != {
        "gesture_hip_flexion_extension_deg":-10.0,
        "gesture_hip_abduction_adduction_deg":-20.0,
        "gesture_ankle_plantar_dorsiflexion_deg":44.0,
    }:
        raise ValueError("Frozen 10.11.2 selected lower parameters changed.")
    if not lower.get("geometry_must_repass_source_gates",False):
        raise ValueError("Frozen lower geometry must repass source gates.")

    upper=contract["upper_body"]
    if upper["arm_source_semantics"] != "BRAS_BAS_DERIVED_LOW_OVAL":
        raise ValueError("10.11.3 arm semantics changed.")
    search=upper["search"]
    if len(search["upper_arm_abduction_adduction_deg"]) != 3:
        raise ValueError("Shoulder search must remain three candidates.")
    if len(search["forearm_flexion_extension_deg"]) != 3:
        raise ValueError("Elbow search must remain three candidates.")
    if max(search["upper_arm_abduction_adduction_deg"]) > float(
        upper["second_position_guard"][
            "maximum_upper_arm_abduction_adduction_deg"
        ]
    ):
        raise ValueError("Low-oval search approaches second position.")

    bow=upper["bow"]
    if bow["canonical_axis"] != "X":
        raise ValueError("Reverence bow must remain canonical-X.")
    if abs(sum(float(x["weight"]) for x in bow["trunk_routes"])-1.0) > 1e-9:
        raise ValueError("Trunk route weights must sum to one.")
    if float(bow["trunk_extra_flexion_deg"]) > 20.0:
        raise ValueError("Trunk bow grew too large.")
    if float(bow["neck_flexion_deg"]) > 6.0:
        raise ValueError("Neck bow grew too large.")
    if float(bow["head_flexion_deg"]) > 10.0:
        raise ValueError("Head bow grew too large.")

    targets=contract["visual_geometry_targets"]
    if float(targets["hand_gap_hand_chain_fraction_min"]) < 0.15:
        raise ValueError("Hand-gap minimum is too small.")
    if float(targets["hand_gap_hand_chain_fraction_max"]) > 0.65:
        raise ValueError("Hand-gap maximum is too large.")
    ideal=float(targets["hand_gap_hand_chain_fraction_ideal"])
    if not (
        float(targets["hand_gap_hand_chain_fraction_min"])
        <= ideal
        <= float(targets["hand_gap_hand_chain_fraction_max"])
    ):
        raise ValueError("Ideal hand gap is outside accepted range.")

    validation=contract["validation"]
    if float(validation["frozen_lower_chain_local_matrix_error_max"]) > 1e-6:
        raise ValueError("Frozen lower-chain gate is too loose.")
    for key in (
        "all_arm_joint_values_within_preferred_envelope",
        "frozen_lower_geometry_must_repass",
        "hand_centerline_crossing_forbidden",
        "no_centerline_projection_allowed",
        "no_permanent_constraints",
        "imported_action_must_be_cleared",
        "report_json_serializable_required",
    ):
        if not validation.get(key,False):
            raise ValueError(f"10.11.3 validation gate changed: {key}.")

    policy=contract["policy"]
    for key in (
        "static_pose_only","lower_body_redesign_forbidden",
        "animation_forbidden","world_turn_forbidden",
        "run_handoff_forbidden","music_sync_forbidden",
        "gameplay_changes_forbidden","glb_export_forbidden",
    ):
        if not policy.get(key,False):
            raise ValueError(f"10.11.3 scope gate changed: {key}.")


def arm_candidate_parameter_sets(contract: dict):
    validate_contract(contract)
    search=contract["upper_body"]["search"]
    for abduction,elbow in itertools.product(
        search["upper_arm_abduction_adduction_deg"],
        search["forearm_flexion_extension_deg"],
    ):
        yield {
            "upper_arm_abduction_adduction_deg":float(abduction),
            "forearm_flexion_extension_deg":float(elbow),
        }


def build_arm_state(contract: dict, parameters: dict) -> dict:
    validate_contract(contract)
    fixed=contract["upper_body"]["fixed"]
    dofs={}
    for side in ("left","right"):
        dofs[f"{side}_upper_arm"]={
            "flexion_extension":float(
                fixed["upper_arm_flexion_extension_deg"]
            ),
            "abduction_adduction":float(
                parameters["upper_arm_abduction_adduction_deg"]
            ),
            "internal_external_rotation":float(
                fixed["upper_arm_internal_external_rotation_deg"]
            ),
        }
        dofs[f"{side}_forearm"]={
            "flexion_extension":float(
                parameters["forearm_flexion_extension_deg"]
            ),
            "pronation_supination":float(
                fixed["forearm_pronation_supination_deg"]
            ),
        }
        dofs[f"{side}_hand"]={
            "flexion_extension":float(
                fixed["hand_flexion_extension_deg"]
            ),
            "radial_ulnar_deviation":float(
                fixed["hand_radial_ulnar_deviation_deg"]
            ),
        }
    return {
        "pose":"reverence_low_oval",
        "joint_dofs":dofs,
        "scalars":{},
    }


def preferred_envelope_violations(state: dict, constraints: dict) -> list[str]:
    violations=[]
    for canonical_name,dofs in state["joint_dofs"].items():
        suffix=canonical_name.split("_",1)[1]
        joint_class=ARM_JOINT_CLASSES[suffix]
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
