"""Phase 10.11.1 opening-reverence acknowledgement-pose helpers."""

from __future__ import annotations


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.11.1":
        raise ValueError("10.11.1 phase mismatch.")
    if contract.get("contract_id") != (
        "opening_reverence_acknowledgement_pose_v1"
    ):
        raise ValueError("10.11.1 contract id mismatch.")

    source=contract["source_pose_authority"]
    if source["lower_body_source_phase"] != "10.8.1":
        raise ValueError("Acknowledgement lower source must remain Phase 10.8.1.")
    if (
        source["lower_body_source_contract_id"]
        != "foundation_motion_fifth_to_plie_v1"
    ):
        raise ValueError("Acknowledgement lower motion contract changed.")
    if int(source["lower_body_sample_frame"]) != 31:
        raise ValueError("Acknowledgement demi-plié sample frame changed.")
    if source["arm_pose"] != "bras_bas":
        raise ValueError("Acknowledgement arm source must remain bras_bas.")
    if (
        source["explicit_arm_chain_local_matrix_authority"]
        != "EXACT_ACCEPTED_BRAS_BAS"
    ):
        raise ValueError("Accepted bras_bas arm authority changed.")
    if (
        source.get("arm_motion_contract_id")
        != "foundation_motion_bras_bas_to_en_avant_v1"
    ):
        raise ValueError("Reverence arm-motion contract authority changed.")
    if (
        source.get("contextual_clearance_adaptation")
        != "REUSE_ACCEPTED_MINIMAL_DEFORMED_MESH_SHOULDER_PROJECTION"
    ):
        raise ValueError("Reverence clearance adaptation authority changed.")

    overlay=contract["acknowledgement_overlay"]
    if overlay["canonical_axis"] != "X":
        raise ValueError("Acknowledgement flexion must use canonical X.")
    if overlay.get("independently_authored_arm_rotation_forbidden") is not True:
        raise ValueError("Independent arm authoring must remain forbidden.")
    if overlay.get("independently_authored_leg_rotation_forbidden") is not True:
        raise ValueError("Independent leg authoring must remain forbidden.")
    routes=overlay["trunk_routes"]
    if [item["bone"] for item in routes] != [
        "spine_lower","spine_mid","chest"
    ]:
        raise ValueError("Trunk route changed.")
    if abs(sum(float(item["weight"]) for item in routes)-1.0) > 1e-9:
        raise ValueError("Trunk route weights must sum to 1.")

    validation=contract["validation"]
    if float(validation["lower_contact_chain_local_matrix_error_max"]) > 1e-6:
        raise ValueError("Lower-chain gate is too loose.")
    if float(validation["arm_nonshoulder_chain_local_matrix_error_max"]) > 1e-6:
        raise ValueError("Non-shoulder arm-chain gate is too loose.")
    if float(validation["shoulder_clearance_correction_deg_max"]) > 3.0:
        raise ValueError("Shoulder clearance correction exceeds 3 degrees.")
    if float(validation["clearance_target_side_offset"]) < 0.0001:
        raise ValueError("Reverence clearance target may not drop below 1e-4.")
    if not validation.get("shoulder_only_contextual_adaptation_required",False):
        raise ValueError("Contextual adaptation must remain shoulder-only.")
    if not validation.get("full_foot_contact_required",False):
        raise ValueError("Full-foot contact must remain required.")
    if not validation.get("hand_centerline_crossing_forbidden",False):
        raise ValueError("Hand centerline crossing must remain forbidden.")
    if float(overlay["trunk_extra_flexion_deg"]) > float(
        validation["trunk_extra_flexion_deg_max"]
    ):
        raise ValueError("Trunk acknowledgement flexion exceeds contract.")
    if float(overlay["neck_flexion_deg"]) > float(
        validation["neck_flexion_deg_max"]
    ):
        raise ValueError("Neck acknowledgement flexion exceeds contract.")
    if float(overlay["head_flexion_deg"]) > float(
        validation["head_flexion_deg_max"]
    ):
        raise ValueError("Head acknowledgement flexion exceeds contract.")

    if contract["facing"]["audience_direction_authority"] != (
        "CANONICAL_BODY_FRAME_FRONT"
    ):
        raise ValueError("Audience-facing authority changed.")

    policy=contract["policy"]
    for key in (
        "static_pose_only","animation_forbidden","reverence_timing_forbidden",
        "world_turn_forbidden","run_handoff_forbidden","music_sync_forbidden",
        "gameplay_changes_forbidden","glb_export_forbidden"
    ):
        if not policy.get(key,False):
            raise ValueError(f"10.11.1 scope gate changed: {key}.")
