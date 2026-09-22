"""Phase 10.9.2 lower-body foundation composition helpers."""

from __future__ import annotations


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.9.2":
        raise ValueError("10.9.2 contract phase mismatch.")
    if contract.get("contract_id") != (
        "foundation_lower_composition_fifth_plie_releve_v1"
    ):
        raise ValueError("10.9.2 contract id mismatch.")

    sequence = contract["sequence"]
    if len(sequence) != 2:
        raise ValueError("10.9.2 must compose exactly two primitives.")

    first, second = sequence
    if (
        first["source_phase"],
        first["start_pose"],
        first["end_pose"],
        int(first["frame_start"]),
        int(first["frame_end"]),
    ) != ("10.8.1", "fifth", "plie", 1, 61):
        raise ValueError("First lower-body composition segment changed.")
    if (
        second["source_phase"],
        second["start_pose"],
        second["end_pose"],
        int(second["frame_start"]),
        int(second["frame_end"]),
    ) != ("10.8.2", "plie", "releve", 61, 121):
        raise ValueError("Second lower-body composition segment changed.")

    if first["end_pose"] != second["start_pose"]:
        raise ValueError("Lower-body segments do not share plié.")
    if int(first["frame_end"]) != int(second["frame_start"]):
        raise ValueError("Lower-body segments do not share one boundary frame.")

    timeline = contract["timeline"]
    if int(timeline["fps"]) != 30:
        raise ValueError("10.9.2 must remain 30 fps.")
    if int(timeline["frame_start"]) != 1:
        raise ValueError("10.9.2 frame start changed.")
    if int(timeline["shared_boundary_frame"]) != 61:
        raise ValueError("10.9.2 boundary frame changed.")
    if int(timeline["frame_end"]) != 121:
        raise ValueError("10.9.2 frame end changed.")
    if timeline["boundary_pose"] != "plie":
        raise ValueError("10.9.2 boundary pose changed.")
    if int(timeline["inserted_hold_frames"]) != 0:
        raise ValueError("10.9.2 may not insert a boundary hold.")

    authority = contract["authority"]
    if not authority.get("composition_only", False):
        raise ValueError("10.9.2 must remain composition-only.")
    if not authority.get(
        "source_primitive_math_reimplementation_forbidden",
        False,
    ):
        raise ValueError("Accepted lower primitive math may not be rewritten.")
    if not authority.get(
        "accepted_trunk_hierarchy_motion_preserved",
        False,
    ):
        raise ValueError("Accepted trunk hierarchy motion must be preserved.")
    if not authority.get("glb_export_forbidden", False):
        raise ValueError("10.9.2 may not export GLB.")

    validation = contract["validation"]
    if float(validation["shared_boundary_local_matrix_error_max"]) > 1e-6:
        raise ValueError("Shared plié boundary gate is too loose.")
    if float(validation["boundary_output_local_matrix_error_max"]) > 1e-6:
        raise ValueError("Boundary output gate is too loose.")
    if float(validation["root_horizontal_translation_max"]) > 1e-5:
        raise ValueError("Root horizontal gate is too loose.")
    if float(validation["root_descent_monotonic_epsilon"]) > 1e-4:
        raise ValueError("Descent epsilon is too loose.")
    if float(validation["root_rise_monotonic_epsilon"]) > 1e-4:
        raise ValueError("Rise epsilon is too loose.")
    if float(validation["heel_lift_monotonic_epsilon"]) > 1e-4:
        raise ValueError("Heel-lift epsilon is too loose.")
    if not validation.get("sample_every_frame", False):
        raise ValueError("10.9.2 must sample every frame.")
    if list(validation["boundary_frames"]) != [60,61,62]:
        raise ValueError("Boundary diagnostic frame set changed.")
    if not validation.get("no_duplicate_boundary_key_authority", False):
        raise ValueError("Boundary key authority must remain single-source.")


def expected_frame_count(contract: dict) -> int:
    validate_contract(contract)
    t=contract["timeline"]
    return int(t["frame_end"])-int(t["frame_start"])+1


def segment_frame_counts(contract: dict) -> tuple[int,int]:
    validate_contract(contract)
    first,second=contract["sequence"]
    return (
        int(first["frame_end"])-int(first["frame_start"])+1,
        int(second["frame_end"])-int(second["frame_start"]),
    )
