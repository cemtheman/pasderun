"""Phase 10.6.6 canonical-pose to calibrated-rig orientation retarget."""

from __future__ import annotations

import copy
import math

from canonical_math import (
    dot,
    mat_mul,
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


SEMANTIC_LENGTH_AXIS_JOINT_CLASSES = {
    "shoulder_ball",
    "elbow_twist",
    "wrist_2dof",
    "hip_ball",
    "knee_hinge",
    "ankle_2dof",
    "mtp_hinge",
}


def _semantic_roll_offset_y(bone: dict) -> float:
    """Extract only calibrated rest roll around the canonical length axis.

    The full canonical-to-rig bind may contain a rest-pose swing because the
    imported model's rest limb direction is not the semantic canonical rest
    direction. Applying that full swing to an already solved absolute pose
    rotates the requested shoulder->elbow / hip->knee direction a second time.
    Keep only the axial roll component here.
    """
    canonical_rest = _rest_basis(bone)
    rig_rest = _rig_rest_basis(bone)
    relative = mat_mul(transpose(canonical_rest), rig_rest)
    numerator = float(relative[0][2]) - float(relative[2][0])
    denominator = float(relative[0][0]) + float(relative[2][2])
    return math.degrees(math.atan2(numerator, denominator))


def _rig_target_from_canonical_pose(
    canonical_pose: list[list[float]],
    bone: dict,
    preserve_semantic_length_axis: bool,
) -> tuple[list[list[float]], str, float]:
    if (
        preserve_semantic_length_axis
        and bone["joint_class"] in SEMANTIC_LENGTH_AXIS_JOINT_CLASSES
    ):
        roll_deg = _semantic_roll_offset_y(bone)
        desired = mat_mul(
            canonical_pose,
            axis_rotation("Y", roll_deg),
        )
        return desired, "SEMANTIC_LENGTH_AXIS_PRESERVED", roll_deg

    desired = mat_mul(_bind_basis(bone), canonical_pose)
    return desired, "FULL_REST_BIND", 0.0


def _canonical_roundtrip_from_rig_target(
    rig_target: list[list[float]],
    bone: dict,
    retarget_mode: str,
    semantic_roll_offset_deg: float,
) -> list[list[float]]:
    if retarget_mode == "SEMANTIC_LENGTH_AXIS_PRESERVED":
        return mat_mul(
            rig_target,
            axis_rotation("Y", -semantic_roll_offset_deg),
        )
    return mat_mul(transpose(_bind_basis(bone)), rig_target)


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


def _wrist_2dof_target_basis(
    desired_length_direction: list[float],
    parent_pose_basis: list[list[float]],
    parent_rest_basis: list[list[float]],
    hand_rest_basis: list[list[float]],
    constraint_profile: dict,
    axis_contract: dict,
) -> tuple[list[list[float]], dict]:
    direction = normalize(desired_length_direction)
    rest_local = mat_mul(
        transpose(parent_rest_basis),
        hand_rest_basis,
    )
    base = mat_mul(parent_pose_basis, rest_local)

    limits = constraint_profile["joint_limits"]["wrist_2dof"]["dofs"]
    flexion = limits["flexion_extension"]["preferred"]
    deviation = limits["radial_ulnar_deviation"]["preferred"]
    fmin = float(flexion["min"])
    fmax = float(flexion["max"])
    dmin = float(deviation["min"])
    dmax = float(deviation["max"])

    local_direction = [
        dot(
            [base[row][column] for row in range(3)],
            direction,
        )
        for column in range(3)
    ]
    ux, uy, uz = [float(value) for value in local_direction]

    ideal_flexion = math.degrees(math.atan2(uz, uy))
    flexion_candidates = [fmin, fmax]
    if fmin <= ideal_flexion <= fmax:
        flexion_candidates.append(ideal_flexion)

    def flexion_score(value: float) -> float:
        angle = math.radians(value)
        return uy * math.cos(angle) + uz * math.sin(angle)

    solved_flexion = max(
        flexion_candidates,
        key=lambda value: (
            flexion_score(value),
            -abs(value),
        ),
    )
    flexion_angle = math.radians(solved_flexion)
    projected_yz = (
        uy * math.cos(flexion_angle)
        + uz * math.sin(flexion_angle)
    )

    ideal_deviation = math.degrees(
        math.atan2(-ux, projected_yz)
    )
    deviation_candidates = [dmin, dmax]
    if dmin <= ideal_deviation <= dmax:
        deviation_candidates.append(ideal_deviation)

    def deviation_score(value: float) -> float:
        angle = math.radians(value)
        return (
            -ux * math.sin(angle)
            + projected_yz * math.cos(angle)
        )

    solved_deviation = max(
        deviation_candidates,
        key=lambda value: (
            deviation_score(value),
            -abs(value),
        ),
    )

    delta = mat_mul(
        axis_rotation("X", solved_flexion),
        axis_rotation("Z", solved_deviation),
    )
    target = mat_mul(base, delta)
    target_y = normalize([target[row][1] for row in range(3)])
    alignment = dot(target_y, direction)

    evidence = {
        "solver_method": "ANALYTIC_RECTANGULAR_PROJECTION",
        "flexion_extension_deg": round(
            float(solved_flexion),
            10,
        ),
        "radial_ulnar_deviation_deg": round(
            float(solved_deviation),
            10,
        ),
        "semantic_alignment_dot": round(
            float(alignment),
            12,
        ),
        "preferred_envelope": {
            "flexion_extension": {
                "min": fmin,
                "max": fmax,
            },
            "radial_ulnar_deviation": {
                "min": dmin,
                "max": dmax,
            },
        },
        "preferred_envelope_status": "PASS",
        "independent_axial_hand_roll": "BLOCKED",
    }
    return target, evidence

def _upper_limb_target_bases(
    state: dict,
    canonical_profile: dict,
    constraint_profile: dict,
    axis_contract: dict,
) -> tuple[dict[str, list[list[float]]], dict]:
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
        return {}, {}

    frame = canonical_profile["body_frame"]["declared_axes_armature_local"]
    front = frame["front"]
    up = frame["up"]
    left = frame["left"]
    targets = {}
    hand_evidence = {}

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

            if role == "hand":
                parent_name = f"{side}_forearm"
                if parent_name not in targets:
                    raise RigRetargetRejected(
                        f"{bone_name}: posed forearm frame is unavailable."
                    )
                bones = canonical_profile["canonical_bones"]
                basis, wrist_evidence = _wrist_2dof_target_basis(
                    direction,
                    targets[parent_name],
                    _rest_basis(bones[parent_name]),
                    _rest_basis(bones[bone_name]),
                    constraint_profile,
                    axis_contract,
                )
                hand_evidence[bone_name] = wrist_evidence
            else:
                basis = basis_from_length_and_front(
                    direction,
                    front,
                    up,
                    left,
                )

                roll = axis_contract["upper_limb_roll"][role]
                source_dof = roll["source_dof"]
                if source_dof is not None:
                    dof_values = state.get("joint_dofs", {}).get(
                        bone_name,
                        {},
                    )
                    angle = float(
                        dof_values.get(source_dof, 0.0)
                    )
                    basis = local_twist_y(basis, angle)

            targets[bone_name] = basis

    return targets, hand_evidence


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
    constraint_profile: dict,
    axis_contract: dict,
) -> tuple[dict, dict, dict]:
    bones = canonical_profile["canonical_bones"]
    order = _topological_order(canonical_profile)
    arm_targets, hand_evidence = _upper_limb_target_bases(
        state,
        canonical_profile,
        constraint_profile,
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

    return posed, local_deltas, hand_evidence


def _rig_pose_from_canonical(
    canonical_pose_bases: dict,
    canonical_profile: dict,
    thresholds: dict,
    preserve_semantic_length_axis: bool = False,
) -> tuple[dict, dict]:
    bones = canonical_profile["canonical_bones"]
    order = _topological_order(canonical_profile)
    rig_pose = {}
    evidence = {}

    for name in order:
        bone = bones[name]
        canonical_pose = canonical_pose_bases[name]
        rig_rest = _rig_rest_basis(bone)
        desired, retarget_mode, semantic_roll_offset_deg = (
            _rig_target_from_canonical_pose(
                canonical_pose,
                bone,
                preserve_semantic_length_axis,
            )
        )

        validate_rotation_matrix(
            desired,
            thresholds["orthogonality_max_error"],
            thresholds["determinant_min"],
            thresholds["determinant_max"],
        )

        roundtrip = _canonical_roundtrip_from_rig_target(
            desired,
            bone,
            retarget_mode,
            semantic_roll_offset_deg,
        )
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

        canonical_y = normalize(
            [canonical_pose[row][1] for row in range(3)]
        )
        desired_y = normalize([desired[row][1] for row in range(3)])
        semantic_length_alignment = (
            dot(canonical_y, desired_y)
            if retarget_mode == "SEMANTIC_LENGTH_AXIS_PRESERVED"
            else None
        )

        rig_pose[name] = {
            "rig_bone": bone["rig_bone"],
            "retarget_mode": retarget_mode,
            "semantic_roll_offset_deg": round(
                float(semantic_roll_offset_deg),
                8,
            ),
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
            "retarget_mode": retarget_mode,
            "semantic_length_axis_alignment_dot": (
                round(float(semantic_length_alignment), 10)
                if semantic_length_alignment is not None
                else None
            ),
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
    constraint_profile: dict,
    axis_contract: dict,
) -> dict:
    if solution["validation"]["status"] != "PASS":
        raise RigRetargetRejected("Unvalidated canonical pose cannot retarget.")

    state = solution["state"]
    thresholds = axis_contract["thresholds"]
    canonical_bases, canonical_local_deltas, hand_wrist_evidence = (
        _canonical_pose_bases(
            state,
            canonical_profile,
            constraint_profile,
            axis_contract,
        )
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
        preserve_semantic_length_axis=True,
    )
    semantic_length_alignment = {
        name: item["semantic_length_axis_alignment_dot"]
        for name, item in rig_evidence.items()
        if item["semantic_length_axis_alignment_dot"] is not None
    }
    semantic_minimum = float(
        thresholds["semantic_limb_length_axis_alignment_min_dot"]
    )
    if any(
        value < semantic_minimum
        for value in semantic_length_alignment.values()
    ):
        raise RigRetargetRejected(
            "Semantic limb length-axis preservation failed: "
            f"{semantic_length_alignment}"
        )

    arm_alignment = _arm_alignment_evidence(
        state,
        canonical_bases,
        canonical_profile,
    )
    minimum_alignment = float(
        thresholds["arm_length_axis_alignment_min_dot"]
    )
    hard_arm_alignment = {
        name: value
        for name, value in arm_alignment.items()
        if not name.endswith("_hand")
    }
    if any(
        value < minimum_alignment
        for value in hard_arm_alignment.values()
    ):
        raise RigRetargetRejected(
            "Upper-arm/forearm length-axis alignment failed: "
            f"{hard_arm_alignment}"
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
            "hand_mesh_spacing_contract",
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
            "hard_arm_length_axis_alignment_dot": hard_arm_alignment,
            "hand_wrist_solution": hand_wrist_evidence,
            "hand_semantic_direction_is_preference": True,
            "hand_wrist_preferred_envelope_pass": True,
            "middle_fingertip_visual_authority": "DEFERRED_TO_BLENDER_DEFORMED_MESH",
            "semantic_limb_length_axis_alignment_dot": (
                semantic_length_alignment
            ),
            "semantic_limb_length_axis_preservation_pass": True,
            "orientation_retarget_only": True,
            "root_translation_applied": False,
            "contact_translation_applied": False,
        },
    }
