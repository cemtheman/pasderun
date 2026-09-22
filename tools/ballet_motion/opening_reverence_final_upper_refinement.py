"""Phase 10.11.4 reverence upper-body expression refinement."""

from __future__ import annotations


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.11.4":
        raise ValueError("10.11.4 phase mismatch.")
    if contract.get("contract_id") != (
        "opening_reverence_final_upper_refinement_v1"
    ):
        raise ValueError("10.11.4 contract id mismatch.")

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
    if upper["arm_source_semantics"] != "EXPLICIT_REVERENCE_LOW_FORWARD_OVAL":
        raise ValueError("10.11.4 arm semantics changed.")
    authority=upper["arm_source_authority"]
    if authority["start_pose"] != "bras_bas":
        raise ValueError("10.11.4 arm start authority changed.")
    if authority["upper_bound_reference_pose"] != "en_avant":
        raise ValueError("10.11.4 arm en-avant upper-bound authority changed.")
    if authority["endpoint_authority"] != "PHASE_10_6_ACCEPTED_REALIZATION":
        raise ValueError("Accepted arm endpoint authority changed.")
    if authority["interpolation_space"] != "LOCAL_MATRIX_BASIS":
        raise ValueError("Arm interpolation space changed.")
    if authority["shoulder_elbow_rotation"] != "QUATERNION_SHORTEST_ARC_SLERP":
        raise ValueError("Arm rotation interpolation changed.")
    if authority["wrist_policy"] != "EXACT_BRAS_BAS":
        raise ValueError("Wrist policy changed.")
    if authority["fingers_policy"] != "EXACT_BRAS_BAS":
        raise ValueError("Finger policy changed.")

    selected=upper["selected_reverence_authority"]
    if selected["mode"] != "EXPLICIT_REVERENCE_GAP_WITH_SEMANTIC_CARRIAGE":
        raise ValueError("Selected reverence authority mode changed.")
    if selected["source_pose"] != "bras_bas":
        raise ValueError("Selected reverence source pose changed.")
    if selected["reference_pose"] != "en_avant":
        raise ValueError("Selected reverence reference pose changed.")
    if abs(float(selected["target_gap_shoulder_width_fraction"])-0.36) > 1e-9:
        raise ValueError("Selected reverence hand gap changed.")
    if abs(float(selected["carriage_progress"])-0.30) > 1e-9:
        raise ValueError("Selected reverence carriage changed.")
    if selected["elbow_pole_policy"] != "EXACT_BRAS_BAS":
        raise ValueError("Selected reverence elbow-pole policy changed.")
    if selected["joint_dofs_policy"] != "EXACT_BRAS_BAS":
        raise ValueError("Selected reverence joint-DOF policy changed.")
    if selected["gap_authority"] != "DEFORMED_HAND_MESH_PRIMARY_SHOULDER_SWEEP":
        raise ValueError("Selected reverence gap authority changed.")
    if not selected.get("canonical_solver_required",False):
        raise ValueError("Selected reverence canonical solver requirement changed.")
    if not selected.get("calibrated_retarget_required",False):
        raise ValueError("Selected reverence retarget requirement changed.")
    if selected.get("human_visual_selection") != "forward_30":
        raise ValueError("Selected reverence human visual choice changed.")
    if not authority.get("diagnostic_reference_only",False):
        raise ValueError("Endpoint interpolation authority must remain diagnostic-only.")

    bow=upper["bow"]
    if bow["canonical_axis"] != "X":
        raise ValueError("Reverence bow must remain canonical-X.")
    if abs(sum(float(x["weight"]) for x in bow["trunk_routes"])-1.0) > 1e-9:
        raise ValueError("Trunk route weights must sum to one.")
    if float(bow["trunk_extra_flexion_deg"]) > 28.0:
        raise ValueError("Trunk bow grew too large.")
    if float(bow["neck_flexion_deg"]) > 8.0:
        raise ValueError("Neck bow grew too large.")
    if float(bow["head_flexion_deg"]) > 12.0:
        raise ValueError("Head bow grew too large.")

    targets=contract["visual_geometry_targets"]
    if (
        targets["metric_authority"]
        != "SHOULDER_MIDPOINT_BODY_FRAME_LEFT_AXIS"
    ):
        raise ValueError("Reverence hand-geometry metric authority changed.")
    if float(targets["hand_gap_shoulder_width_fraction_min"]) < 0.20:
        raise ValueError("Hand-gap minimum is too small.")
    if float(targets["hand_gap_shoulder_width_fraction_max"]) > 0.65:
        raise ValueError("Hand-gap maximum is too large.")
    if float(
        targets[
            "hand_midpoint_asymmetry_shoulder_width_fraction_max"
        ]
    ) > 0.10:
        raise ValueError("Hand midpoint asymmetry gate is too loose.")
    ideal=float(targets["hand_gap_shoulder_width_fraction_ideal"])
    if not (
        float(targets["hand_gap_shoulder_width_fraction_min"])
        <= ideal
        <= float(targets["hand_gap_shoulder_width_fraction_max"])
    ):
        raise ValueError("Ideal hand gap is outside accepted range.")

    validation=contract["validation"]
    if float(validation["frozen_lower_chain_local_matrix_error_max"]) > 1e-6:
        raise ValueError("Frozen lower-chain gate is too loose.")
    for key in (
        "selected_explicit_reverence_authority_required",
        "frozen_lower_geometry_must_repass",
        "hand_centerline_crossing_forbidden",
        "no_centerline_projection_allowed",
        "no_permanent_constraints",
        "imported_action_must_be_cleared",
        "report_json_serializable_required",
    ):
        if not validation.get(key,False):
            raise ValueError(f"10.11.4 validation gate changed: {key}.")

    policy=contract["policy"]
    for key in (
        "static_pose_only","lower_body_redesign_forbidden",
        "animation_forbidden","world_turn_forbidden",
        "run_handoff_forbidden","music_sync_forbidden",
        "gameplay_changes_forbidden","glb_export_forbidden",
    ):
        if not policy.get(key,False):
            raise ValueError(f"10.11.4 scope gate changed: {key}.")

