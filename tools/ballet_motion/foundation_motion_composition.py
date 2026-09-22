"""Phase 10.9.1 foundation arm-composition helpers."""

from __future__ import annotations


def validate_contract(contract: dict) -> None:
    if contract.get("phase") != "10.9.1":
        raise ValueError("10.9.1 contract phase mismatch.")
    if contract.get("contract_id") != (
        "foundation_arm_composition_bras_bas_en_avant_second_v1"
    ):
        raise ValueError("10.9.1 contract id mismatch.")

    sequence = contract["sequence"]
    if len(sequence) != 2:
        raise ValueError("10.9.1 must compose exactly two accepted primitives.")

    first, second = sequence
    if (
        first["source_phase"],
        first["start_pose"],
        first["end_pose"],
        int(first["frame_start"]),
        int(first["frame_end"]),
    ) != ("10.7.1", "bras_bas", "en_avant", 1, 61):
        raise ValueError("First composition segment changed.")
    if (
        second["source_phase"],
        second["start_pose"],
        second["end_pose"],
        int(second["frame_start"]),
        int(second["frame_end"]),
    ) != ("10.7.2", "en_avant", "second", 61, 121):
        raise ValueError("Second composition segment changed.")

    if first["end_pose"] != second["start_pose"]:
        raise ValueError("Composition segments do not share an endpoint pose.")
    if int(first["frame_end"]) != int(second["frame_start"]):
        raise ValueError("Composition segments do not share one boundary frame.")

    timeline = contract["timeline"]
    if int(timeline["fps"]) != 30:
        raise ValueError("10.9.1 proof must remain at 30 fps.")
    if int(timeline["frame_start"]) != 1:
        raise ValueError("10.9.1 frame start changed.")
    if int(timeline["shared_boundary_frame"]) != 61:
        raise ValueError("10.9.1 shared boundary changed.")
    if int(timeline["frame_end"]) != 121:
        raise ValueError("10.9.1 frame end changed.")
    if timeline["boundary_pose"] != "en_avant":
        raise ValueError("10.9.1 boundary pose changed.")
    if int(timeline["inserted_hold_frames"]) != 0:
        raise ValueError("Composition may not insert a boundary hold.")

    authority = contract["authority"]
    if not authority.get("composition_only", False):
        raise ValueError("10.9.1 must remain composition-only.")
    if not authority.get(
        "source_primitive_math_reimplementation_forbidden",
        False,
    ):
        raise ValueError("Accepted primitive math may not be reimplemented.")
    if not authority.get("lower_body_motion_forbidden", False):
        raise ValueError("10.9.1 may not author lower-body motion.")
    if not authority.get("glb_export_forbidden", False):
        raise ValueError("10.9.1 may not export GLB.")

    validation = contract["validation"]
    if float(validation["shared_boundary_local_matrix_error_max"]) > 1e-6:
        raise ValueError("Shared-boundary matrix gate is too loose.")
    if float(validation["boundary_output_local_matrix_error_max"]) > 1e-6:
        raise ValueError("Boundary output matrix gate is too loose.")
    if float(validation["lower_body_locked_local_matrix_error_max"]) > 1e-6:
        raise ValueError("Lower-body lock gate is too loose.")
    if not validation.get("sample_every_frame", False):
        raise ValueError("10.9.1 must sample every frame.")
    if list(validation["boundary_frames"]) != [60, 61, 62]:
        raise ValueError("Boundary diagnostic frame set changed.")
    if not validation.get("no_duplicate_boundary_key_authority", False):
        raise ValueError("Boundary key authority must remain single-source.")


def expected_frame_count(contract: dict) -> int:
    validate_contract(contract)
    timeline = contract["timeline"]
    return int(timeline["frame_end"]) - int(timeline["frame_start"]) + 1


def segment_frame_counts(contract: dict) -> tuple[int, int]:
    validate_contract(contract)
    first, second = contract["sequence"]
    first_count = int(first["frame_end"]) - int(first["frame_start"]) + 1
    # Shared boundary is authored only by the first segment.
    second_count = int(second["frame_end"]) - int(second["frame_start"])
    return first_count, second_count
