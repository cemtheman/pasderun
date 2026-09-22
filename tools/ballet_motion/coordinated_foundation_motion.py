"""Phase 10.10.1 coordinated foundation-motion contract helpers."""

from __future__ import annotations


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.10.1":
        raise ValueError("10.10.1 contract phase mismatch.")
    if contract.get("contract_id") != "coordinated_foundation_motion_v1":
        raise ValueError("10.10.1 contract id mismatch.")

    timeline=contract["timeline"]
    if (
        int(timeline["fps"]),
        int(timeline["frame_start"]),
        int(timeline["shared_boundary_frame"]),
        int(timeline["frame_end"]),
        int(timeline["inserted_hold_frames"]),
    ) != (30,1,61,121,0):
        raise ValueError("10.10.1 timeline changed.")

    if contract["arm_chain"]["poses"] != [
        "bras_bas","en_avant","second"
    ]:
        raise ValueError("Arm chain changed.")
    if contract["lower_chain"]["poses"] != [
        "fifth","plie","releve"
    ]:
        raise ValueError("Lower chain changed.")
    if contract["arm_chain"]["boundary_pose"] != "en_avant":
        raise ValueError("Arm boundary changed.")
    if contract["lower_chain"]["boundary_pose"] != "plie":
        raise ValueError("Lower boundary changed.")

    authority=contract["authority"]
    if authority["motion_authority"] != "SINGLE_HUMANOID_RIG":
        raise ValueError("Single humanoid authority changed.")
    if not authority.get("composition_only",False):
        raise ValueError("10.10.1 must remain composition-only.")
    if not authority.get(
        "source_primitive_math_reimplementation_forbidden",False
    ):
        raise ValueError("Source primitive math may not be reimplemented.")
    if (
        authority["overlap_policy"]
        != "ARM_EXPLICIT_MAY_OVERRIDE_LOWER_HIERARCHY_FOLLOWERS_ONLY"
    ):
        raise ValueError("Authority overlap policy changed.")
    if not authority.get(
        "lower_semantic_driver_overlap_with_arm_forbidden",False
    ):
        raise ValueError("Arm/lower semantic overlap must stay forbidden.")
    if authority["root_contact_authority"] != "LOWER_BODY_CONTACT_SOLVER":
        raise ValueError("Root contact authority changed.")
    if (
        authority.get("coordinated_boundary_clearance_adaptation")
        != "REUSE_ACCEPTED_MINIMAL_DEFORMED_MESH_SHOULDER_PROJECTION"
    ):
        raise ValueError("Coordinated boundary clearance authority changed.")
    if not authority.get(
        "source_endpoint_projection_rule_preserved_outside_shared_boundary",
        False,
    ):
        raise ValueError(
            "Source endpoint projection rule must remain preserved "
            "outside the coordinated shared boundary."
        )
    if not authority.get("glb_export_forbidden",False):
        raise ValueError("10.10.1 may not export GLB.")

    validation=contract["validation"]
    if int(validation["arm_lower_semantic_overlap_count_max"]) != 0:
        raise ValueError("Arm/lower semantic overlap ceiling must be zero.")
    if float(
        validation["shared_arm_boundary_local_matrix_error_max"]
    ) > 1e-6:
        raise ValueError("Arm boundary gate is too loose.")
    if float(
        validation["shared_lower_boundary_local_matrix_error_max"]
    ) > 1e-6:
        raise ValueError("Lower boundary gate is too loose.")
    if float(validation["root_horizontal_translation_max"]) > 1e-5:
        raise ValueError("Root horizontal gate is too loose.")
    if not validation.get("sample_every_frame",False):
        raise ValueError("10.10.1 must sample every frame.")
    if list(validation["boundary_frames"]) != [60,61,62]:
        raise ValueError("Boundary diagnostic frames changed.")
    if not validation.get("no_duplicate_boundary_key_authority",False):
        raise ValueError("Boundary key authority must remain singular.")
    if not validation.get("post_overlay_contact_required",False):
        raise ValueError("Post-overlay foot contact must remain required.")
    if (
        float(
            validation[
                "coordinated_boundary_clearance_projection_max_shoulder_correction_deg"
            ]
        )
        > 3.0
    ):
        raise ValueError("Coordinated boundary shoulder correction exceeds 3 deg.")
    if (
        float(
            validation[
                "coordinated_boundary_nonshoulder_arm_local_matrix_error_max"
            ]
        )
        > 1e-6
    ):
        raise ValueError("Coordinated non-shoulder arm boundary gate is too loose.")
    if (
        int(validation["coordinated_boundary_projection_only_frame"])
        != int(timeline["shared_boundary_frame"])
    ):
        raise ValueError("Coordinated boundary projection frame changed.")


def expected_frame_count(contract: dict) -> int:
    validate_contract(contract)
    t=contract["timeline"]
    return int(t["frame_end"])-int(t["frame_start"])+1
