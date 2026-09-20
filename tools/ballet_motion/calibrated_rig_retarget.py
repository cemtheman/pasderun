"""Phase 10.6.6 canonical-pose to calibrated-rig orientation retarget."""

from __future__ import annotations

import copy

from canonical_math import (
    dot,
    mat_mul,
    mat_vec,
    normalize,
    orthonormalize_basis,
    rotation_matrix_to_quaternion_wxyz,
    rounded_matrix,
    rounded_vector,
    sub,
    transpose,
)
from rig_retarget_math import (
    axis_rotation,
    basis_from_length_and_front,
    identity3,
    local_twist_y,
    matrix_max_error,
    validate_rotation_matrix,
)


class RigRetargetRejected(RuntimeError):
    pass


def _side_sign(bone_name: str) -> float:
    if bone_name.startswith("left_"):
        return 1.0
    if bone_name.startswith("right_"):
        return -1.0
    return 1.0


def _body_vector_to_armature(
    value: list[float],
    canonical_profile: dict,
) -> list[float]:
    frame = canonical_profile["body_frame"]["declared_axes_armature_local"]
    left = frame["left"]
    up = frame["up"]
    front = frame["front"]
    return [
        float(left[i]) * float(value[0])
        + float(up[i]) * float(value[1])
        + float(front[i]) * float(value[2])
        for i in range(3)
    ]


def _body_point_delta_to_armature(
    start: dict,
    end: dict,
    canonical_profile: dict,
) -> list[float]:
    delta = [
        float(end["left"]) - float(start["left"]),
        float(end["up"]) - float(start["up"]),
        float(end["front"]) - float(start["front"]),
    ]
    return _body_vector_to_armature(delta, canonical_profile)


def _rest_basis(bone: dict) -> list[list[float]]:
    return orthonormalize_basis(
        bone["canonical_rest_contract"]["basis_armature_local"]
    )


def _rig_rest_basis(bone: dict) -> list[list[float]]:
    return orthonormalize_basis(bone["rig_rest_basis_armature_local"])


def _bind_basis(bone: dict) -> list[list[float]]:
    return orthonormalize_basis(
        bone["retarget_bind"]["canonical_to_rig_rotation_matrix"]
    )


def _topological_order(canonical_profile: dict) -> list[str]:
    bones = canonical_profile["canonical_bones"]
    remaining = set(bones)
    emitted = []
    while remaining:
        progressed = False
        for name in sorted(remaining):
            parent = bones[name]["parent"]
            if parent is None or parent in emitted:
                emitted.append(name)
                remaining.remove(name)
                progressed = True
                break
        if not progressed:
            raise RigRetargetRejected("Canonical hierarchy is cyclic.")
    return emitted


def _upper_limb_target_bases(
    state: dict,
    canonical_profile: dict,
    axis_contract: dict,
) -> dict[str, list[list[float]]]:
    landmarks = state.get("landmarks", {})
    required = (
        "left_shoulder",
        "left_elbow",
        "left_wrist",
        "left_hand",
        "right_shoulder",
        "right_elbow",
        "right_wrist",
        "right_hand",
    )
    if not all(name in landmarks for name in required):
        return {}

    frame = canonical_profile["body_frame"]["declared_axes_armature_local"]
    front = frame["front"]
    up = frame["up"]
    left = frame["left"]
    targets = {}

    for side in ("left", "right"):
        chains = (
            (
                f"{side}_upper_arm",
                f"{side}_shoulder",
                f"{side}_elbow",
                "upper_arm",
            ),
            (
                f"{side}_forearm",
                f"{side}_elbow",
                f"{side}_wrist",
                "forearm",
            ),
            (
                f"{side}_hand",
                f"{side}_wrist",
                f"{side}_hand",
                "hand",
            ),
        )
        for bone_name, start_name, end_name, role in chains:
            direction = _body_point_delta_to_armature(
                landmarks[start_name],
                landmarks[end_name],
                canonical_profile,
            )
            basis = basis_from_length_and_front(
                direction,
                front,
                up,
                left,
            )

            roll = axis_contract["upper_limb_roll"][role]
            source_dof = roll["source_dof"]
            if source_dof is not None:
                dof_values = state.get("joint_dofs", {}).get(bone_name, {})
                angle = float(dof_values.get(source_dof, 0.0))
                basis = local_twist_y(basis, angle)

            targets[bone_name] = basis

    return targets


def _joint_delta(
    bone_name: str,
    bone: dict,
    state: dict,
    axis_contract: dict,
) -> list[list[float]]:
    joint_class = bone["joint_class"]
    operations = axis_contract["lower_body_joint_axes"].get(
        joint_class,
        [],
    )

    authored = state.get("joint_dofs", {}).get(bone_name, {})
    result = identity3()
    side_factor = _side_sign(bone_name)

    for operation in operations:
        if "dof" in operation:
            dof = operation["dof"]
            if dof not in authored:
                continue
            value = float(authored[dof])
        else:
            derived = operation["derived"]
            side = "left" if bone_name.startswith("left_") else "right"
            turnout = state.get("turnout", {}).get(side, {})
            if derived not in turnout:
                continue
            value = float(turnout[derived])

        angle = value * float(operation["scale"])
        if operation["side_sign"]:
            angle *= side_factor
        result = mat_mul(result, axis_rotation(operation["axis"], angle))

    for scalar_name, route in axis_contract.get(
        "scalar_orientation_routes",
        {},
    ).items():
        scalar_value = state.get("scalars", {}).get(scalar_name)
        if scalar_value is None:
            continue
        for target in route["routes"]:
            if target["bone"] != bone_name:
                continue
            angle = float(scalar_value) * float(target["weight"])
            result = mat_mul(
                result,
                axis_rotation(route["axis"], angle),
            )

    return result


def _canonical_pose_bases(
    state: dict,
    canonical_profile: dict,
    axis_contract: dict,
) -> tuple[dict, dict]:
    bones = canonical_profile["canonical_bones"]
    order = _topological_order(canonical_profile)
    arm_targets = _upper_limb_target_bases(
        state,
        canonical_profile,
        axis_contract,
    )

    posed = {}
    local_deltas = {}
    for name in order:
        bone = bones[name]
        rest = _rest_basis(bone)
        parent = bone["parent"]

        if parent is None:
            parent_pose = None
            local_rest = rest
        else:
            parent_rest = _rest_basis(bones[parent])
            parent_pose = posed[parent]
            local_rest = mat_mul(transpose(parent_rest), rest)

        if name in arm_targets:
            target = arm_targets[name]
            if parent is None:
                delta = mat_mul(transpose(rest), target)
            else:
                desired_local = mat_mul(transpose(parent_pose), target)
                delta = mat_mul(transpose(local_rest), desired_local)
            reconstructed = (
                mat_mul(rest, delta)
                if parent is None
                else mat_mul(mat_mul(parent_pose, local_rest), delta)
            )
            if matrix_max_error(reconstructed, target) > 1e-7:
                raise RigRetargetRejected(
                    f"{name}: canonical target reconstruction failed."
                )
            pose_basis = target
        else:
            delta = _joint_delta(
                name,
                bone,
                state,
                axis_contract,
            )
            pose_basis = (
                mat_mul(rest, delta)
                if parent is None
                else mat_mul(mat_mul(parent_pose, local_rest), delta)
            )

        posed[name] = pose_basis
        local_deltas[name] = delta

    return posed, local_deltas


def _rig_pose_from_canonical(
    canonical_pose_bases: dict,
    canonical_profile: dict,
    thresholds: dict,
) -> tuple[dict, dict]:
    bones = canonical_profile["canonical_bones"]
    order = _topological_order(canonical_profile)
    rig_pose = {}
    evidence = {}

    for name in order:
        bone = bones[name]
        canonical_pose = canonical_pose_bases[name]
        bind = _bind_basis(bone)
        rig_rest = _rig_rest_basis(bone)
        desired = mat_mul(bind, canonical_pose)

        validate_rotation_matrix(
            desired,
            thresholds["orthogonality_max_error"],
            thresholds["determinant_min"],
            thresholds["determinant_max"],
        )

        roundtrip = mat_mul(transpose(bind), desired)
        roundtrip_error = matrix_max_error(roundtrip, canonical_pose)
        if roundtrip_error > float(thresholds["bind_roundtrip_max_error"]):
            raise RigRetargetRejected(
                f"{name}: canonical/rig roundtrip error {roundtrip_error}."
            )

        parent = bone["parent"]
        if parent is None:
            local_delta = mat_mul(transpose(rig_rest), desired)
            reconstructed = mat_mul(rig_rest, local_delta)
        else:
            parent_bone = bones[parent]
            parent_rest = _rig_rest_basis(parent_bone)
            parent_pose = rig_pose[parent]["armature_basis_raw"]
            rest_local = mat_mul(transpose(parent_rest), rig_rest)
            desired_local = mat_mul(transpose(parent_pose), desired)
            local_delta = mat_mul(transpose(rest_local), desired_local)
            reconstructed = mat_mul(
                mat_mul(parent_pose, rest_local),
                local_delta,
            )

        hierarchy_error = matrix_max_error(reconstructed, desired)
        if hierarchy_error > float(
            thresholds["hierarchy_reconstruction_max_error"]
        ):
            raise RigRetargetRejected(
                f"{name}: hierarchy reconstruction error {hierarchy_error}."
            )

        validate_rotation_matrix(
            local_delta,
            thresholds["orthogonality_max_error"],
            thresholds["determinant_min"],
            thresholds["determinant_max"],
        )

        rig_pose[name] = {
            "rig_bone": bone["rig_bone"],
            "armature_basis_raw": desired,
            "armature_basis": rounded_matrix(desired),
            "local_pose_delta_matrix": rounded_matrix(local_delta),
            "local_pose_delta_quaternion_wxyz": rounded_vector(
                rotation_matrix_to_quaternion_wxyz(local_delta)
            ),
        }
        evidence[name] = {
            "canonical_roundtrip_error": round(roundtrip_error, 10),
            "hierarchy_reconstruction_error": round(hierarchy_error, 10),
        }

    return rig_pose, evidence


def _arm_alignment_evidence(
    state: dict,
    canonical_pose_bases: dict,
    canonical_profile: dict,
) -> dict:
    landmarks = state.get("landmarks", {})
    if "left_shoulder" not in landmarks:
        return {}

    result = {}
    for side in ("left", "right"):
        chains = (
            (f"{side}_upper_arm", f"{side}_shoulder", f"{side}_elbow"),
            (f"{side}_forearm", f"{side}_elbow", f"{side}_wrist"),
            (f"{side}_hand", f"{side}_wrist", f"{side}_hand"),
        )
        for bone_name, start_name, end_name in chains:
            segment = normalize(
                _body_point_delta_to_armature(
                    landmarks[start_name],
                    landmarks[end_name],
                    canonical_profile,
                )
            )
            basis = canonical_pose_bases[bone_name]
            length_axis = normalize([basis[row][1] for row in range(3)])
            result[bone_name] = round(dot(segment, length_axis), 10)
    return result


def validate_rest_identity(
    canonical_profile: dict,
    axis_contract: dict,
) -> dict:
    thresholds = axis_contract["thresholds"]
    maximum_bind_error = 0.0
    maximum_local_delta_error = 0.0
    bones = canonical_profile["canonical_bones"]
    identity = identity3()

    rest_pose = {name: _rest_basis(bone) for name, bone in bones.items()}
    rig_pose, _ = _rig_pose_from_canonical(
        rest_pose,
        canonical_profile,
        thresholds,
    )

    for name, bone in bones.items():
        rig_rest = _rig_rest_basis(bone)
        mapped = rig_pose[name]["armature_basis_raw"]
        maximum_bind_error = max(
            maximum_bind_error,
            matrix_max_error(mapped, rig_rest),
        )
        maximum_local_delta_error = max(
            maximum_local_delta_error,
            matrix_max_error(
                rig_pose[name]["local_pose_delta_matrix"],
                identity,
            ),
        )

    limit = float(thresholds["rest_identity_max_error"])
    if maximum_bind_error > limit or maximum_local_delta_error > limit:
        raise RigRetargetRejected(
            "Rest identity failed: "
            f"bind={maximum_bind_error}, local={maximum_local_delta_error}."
        )

    return {
        "max_rig_rest_basis_error": round(maximum_bind_error, 10),
        "max_local_delta_identity_error": round(
            maximum_local_delta_error,
            10,
        ),
    }


def retarget_pose_solution(
    solution: dict,
    canonical_profile: dict,
    axis_contract: dict,
) -> dict:
    if solution["validation"]["status"] != "PASS":
        raise RigRetargetRejected("Unvalidated canonical pose cannot retarget.")

    state = solution["state"]
    thresholds = axis_contract["thresholds"]
    canonical_bases, canonical_local_deltas = _canonical_pose_bases(
        state,
        canonical_profile,
        axis_contract,
    )

    for name, basis in canonical_bases.items():
        validate_rotation_matrix(
            basis,
            thresholds["orthogonality_max_error"],
            thresholds["determinant_min"],
            thresholds["determinant_max"],
        )

    rig_pose, rig_evidence = _rig_pose_from_canonical(
        canonical_bases,
        canonical_profile,
        thresholds,
    )
    arm_alignment = _arm_alignment_evidence(
        state,
        canonical_bases,
        canonical_profile,
    )
    minimum_alignment = float(
        thresholds["arm_length_axis_alignment_min_dot"]
    )
    if any(value < minimum_alignment for value in arm_alignment.values()):
        raise RigRetargetRejected(
            f"Arm length-axis alignment failed: {arm_alignment}"
        )

    canonical_output = {
        name: {
            "armature_basis": rounded_matrix(basis),
            "local_pose_delta_matrix": rounded_matrix(
                canonical_local_deltas[name]
            ),
            "local_pose_delta_quaternion_wxyz": rounded_vector(
                rotation_matrix_to_quaternion_wxyz(
                    canonical_local_deltas[name]
                )
            ),
        }
        for name, basis in canonical_bases.items()
    }

    non_rotational = {
        key: copy.deepcopy(state[key])
        for key in (
            "contacts",
            "turnout",
            "knee_second_toe_error_deg",
            "com",
            "support_polygon",
        )
        if key in state
    }
    translation_scalars = {
        key: value
        for key, value in state.get("scalars", {}).items()
        if key != "trunk_tilt_deg"
    }
    if translation_scalars:
        non_rotational["translation_contact_scalars"] = translation_scalars

    max_roundtrip = max(
        item["canonical_roundtrip_error"]
        for item in rig_evidence.values()
    )
    max_hierarchy = max(
        item["hierarchy_reconstruction_error"]
        for item in rig_evidence.values()
    )

    # Remove private raw matrices from serialized rig output.
    serial_rig_pose = {}
    for name, item in rig_pose.items():
        serial_rig_pose[name] = {
            key: value
            for key, value in item.items()
            if key != "armature_basis_raw"
        }

    return {
        "pose": solution["pose"],
        "canonical_pose": canonical_output,
        "rig_pose": serial_rig_pose,
        "non_rotational_pose_contract": non_rotational,
        "evidence": {
            "bone_count": len(canonical_bases),
            "max_canonical_roundtrip_error": round(max_roundtrip, 10),
            "max_hierarchy_reconstruction_error": round(max_hierarchy, 10),
            "arm_length_axis_alignment_dot": arm_alignment,
            "orientation_retarget_only": True,
            "root_translation_applied": False,
            "contact_translation_applied": False,
        },
    }
