"""Phase 10.6.7 static rig application + contact/root translation proof.

This is the first Phase 10.6 step that applies solved transforms to the
actual imported low_poly_girl armature. It does not render or export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


PHASE = "10.6.7"

SEMANTIC_LENGTH_AXIS_JOINT_CLASSES = {
    "shoulder_ball",
    "elbow_twist",
    "wrist_2dof",
    "hip_ball",
    "knee_hinge",
    "ankle_2dof",
    "mtp_hinge",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--canonical-profile", required=True)
    parser.add_argument("--retarget-profile", required=True)
    parser.add_argument("--constraint-profile", required=True)
    parser.add_argument("--retarget-axis-contract", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def matrix3(values) -> Matrix:
    return Matrix(tuple(tuple(float(value) for value in row) for row in values))


def matrix_max_error(a: Matrix, b: Matrix) -> float:
    return max(
        abs(float(a[row][col]) - float(b[row][col]))
        for row in range(3)
        for col in range(3)
    )


def normalized_basis(matrix: Matrix) -> Matrix:
    result = matrix.to_3x3().normalized()
    if result.determinant() < 0.0:
        raise RuntimeError("Pose basis is not right-handed.")
    return result


def rotation_y(angle_deg: float) -> Matrix:
    angle = math.radians(float(angle_deg))
    c = math.cos(angle)
    s = math.sin(angle)
    return Matrix(
        (
            (c, 0.0, s),
            (0.0, 1.0, 0.0),
            (-s, 0.0, c),
        )
    )


def semantic_roll_offset_y(canonical_bone: dict) -> float:
    canonical_rest = matrix3(
        canonical_bone["canonical_rest_contract"]["basis_armature_local"]
    )
    rig_rest = matrix3(
        canonical_bone["rig_rest_basis_armature_local"]
    )
    relative = canonical_rest.transposed() @ rig_rest
    numerator = float(relative[0][2]) - float(relative[2][0])
    denominator = float(relative[0][0]) + float(relative[2][2])
    return math.degrees(math.atan2(numerator, denominator))


def rig_basis_from_canonical_pose(
    canonical_bone: dict,
    canonical_basis: Matrix,
) -> Matrix:
    if (
        canonical_bone["joint_class"]
        in SEMANTIC_LENGTH_AXIS_JOINT_CLASSES
    ):
        return (
            canonical_basis
            @ rotation_y(semantic_roll_offset_y(canonical_bone))
        )

    bind = matrix3(
        canonical_bone["retarget_bind"][
            "canonical_to_rig_rotation_matrix"
        ]
    )
    return bind @ canonical_basis


def quantile(values: list[float], fraction: float) -> float:
    if not values:
        raise RuntimeError("Cannot measure empty contact sample.")
    ordered = sorted(float(value) for value in values)
    fraction = min(max(float(fraction), 0.0), 1.0)
    position = fraction * (len(ordered) - 1)
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    blend = position - lower
    return ordered[lower] * (1.0 - blend) + ordered[upper] * blend


def median(values: list[float]) -> float:
    return quantile(values, 0.5)


def find_armature(expected_name: str) -> bpy.types.Object:
    armatures = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "ARMATURE"
    ]
    for armature in armatures:
        if armature.name == expected_name:
            return armature
    raise RuntimeError(
        f"Expected armature {expected_name!r}; found "
        f"{sorted(obj.name for obj in armatures)}."
    )


def clear_pose(armature: bpy.types.Object) -> None:
    for pose_bone in armature.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def relevant_mesh_objects(
    armature: bpy.types.Object,
    required_groups: set[str],
) -> list[bpy.types.Object]:
    meshes = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        group_names = {group.name for group in obj.vertex_groups}
        if not (group_names & required_groups):
            continue
        has_armature = any(
            modifier.type == "ARMATURE"
            and modifier.object == armature
            for modifier in obj.modifiers
        )
        if has_armature:
            meshes.append(obj)
    if not meshes:
        raise RuntimeError(
            "No deformed mesh object contains required foot/toe vertex groups."
        )
    return meshes


def collect_weighted_samples(
    meshes: list[bpy.types.Object],
    group_names: set[str],
    minimum_weight: float,
) -> list[tuple[str, int]]:
    samples = []
    for obj in meshes:
        indices = {
            group.index
            for group in obj.vertex_groups
            if group.name in group_names
        }
        if not indices:
            continue
        for vertex in obj.data.vertices:
            weight = max(
                (
                    membership.weight
                    for membership in vertex.groups
                    if membership.group in indices
                ),
                default=0.0,
            )
            if weight >= minimum_weight:
                samples.append((obj.name, int(vertex.index)))
    if not samples:
        raise RuntimeError(
            f"No vertices meet foot/toe weight threshold for {sorted(group_names)}."
        )
    return samples


def evaluated_sample_points(
    armature: bpy.types.Object,
    samples: list[tuple[str, int]],
) -> list[Vector]:
    depsgraph = bpy.context.evaluated_depsgraph_get()
    armature_inverse = armature.matrix_world.inverted()
    grouped: dict[str, list[int]] = {}
    for object_name, vertex_index in samples:
        grouped.setdefault(object_name, []).append(vertex_index)

    points = []
    for object_name, indices in grouped.items():
        source = bpy.data.objects[object_name]
        evaluated = source.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            if max(indices) >= len(mesh.vertices):
                raise RuntimeError(
                    f"Evaluated topology changed for {object_name}."
                )
            transform = armature_inverse @ evaluated.matrix_world
            for vertex_index in indices:
                points.append(transform @ mesh.vertices[vertex_index].co)
        finally:
            evaluated.to_mesh_clear()
    return points


def classify_contact_samples(
    armature: bpy.types.Object,
    samples: list[tuple[str, int]],
    front_axis: Vector,
    rear_fraction: float,
    fore_fraction: float,
) -> dict[str, list[tuple[str, int]]]:
    points = evaluated_sample_points(armature, samples)
    paired = list(zip(samples, points))
    paired.sort(key=lambda item: item[1].dot(front_axis))
    count = len(paired)
    rear_count = max(1, int(math.ceil(count * rear_fraction)))
    fore_count = max(1, int(math.ceil(count * fore_fraction)))
    return {
        "rear": [sample for sample, _point in paired[:rear_count]],
        "fore": [sample for sample, _point in paired[-fore_count:]],
    }


def anchor_height(
    armature: bpy.types.Object,
    samples: list[tuple[str, int]],
    up_axis: Vector,
    low_height_quantile: float,
) -> float:
    points = evaluated_sample_points(armature, samples)
    heights = [point.dot(up_axis) for point in points]
    return quantile(heights, low_height_quantile)


def contact_heights(
    armature: bpy.types.Object,
    anchors: dict,
    up_axis: Vector,
    low_height_quantile: float,
) -> dict:
    return {
        side: {
            region: anchor_height(
                armature,
                region_samples,
                up_axis,
                low_height_quantile,
            )
            for region, region_samples in side_anchors.items()
        }
        for side, side_anchors in anchors.items()
    }


def apply_rotation_deltas(
    armature: bpy.types.Object,
    pose_entry: dict,
) -> None:
    clear_pose(armature)
    for canonical_name, target in pose_entry["rig_pose"].items():
        rig_name = target["rig_bone"]
        pose_bone = armature.pose.bones.get(rig_name)
        if pose_bone is None:
            raise RuntimeError(
                f"Retarget bone missing from imported rig: "
                f"{canonical_name}->{rig_name}"
            )
        matrix = matrix3(target["local_pose_delta_matrix"]).to_4x4()
        pose_bone.matrix_basis = matrix
    bpy.context.view_layer.update()


def canonical_basis_from_rig_pose(
    pose_bone: bpy.types.PoseBone,
    canonical_bone: dict,
) -> Matrix:
    rig_basis = normalized_basis(pose_bone.matrix)
    if (
        canonical_bone["joint_class"]
        in SEMANTIC_LENGTH_AXIS_JOINT_CLASSES
    ):
        return (
            rig_basis
            @ rotation_y(-semantic_roll_offset_y(canonical_bone))
        )

    bind = matrix3(
        canonical_bone["retarget_bind"][
            "canonical_to_rig_rotation_matrix"
        ]
    )
    return bind.transposed() @ rig_basis


def basis_from_columns(x_axis: Vector, y_axis: Vector, z_axis: Vector) -> Matrix:
    return Matrix(
        (
            (x_axis.x, y_axis.x, z_axis.x),
            (x_axis.y, y_axis.y, z_axis.y),
            (x_axis.z, y_axis.z, z_axis.z),
        )
    )


def apply_absolute_rig_rotation_via_matrix_basis(
    armature: bpy.types.Object,
    rig_name: str,
    desired_rig_basis: Matrix,
) -> None:
    pose_bone = armature.pose.bones[rig_name]
    if pose_bone.parent is None:
        rig_rest = armature.data.bones[rig_name].matrix_local.to_3x3().normalized()
        local_delta = rig_rest.transposed() @ desired_rig_basis
    else:
        parent_name = pose_bone.parent.name
        parent_pose = normalized_basis(pose_bone.parent.matrix)
        parent_rest = (
            armature.data.bones[parent_name].matrix_local.to_3x3().normalized()
        )
        rig_rest = (
            armature.data.bones[rig_name].matrix_local.to_3x3().normalized()
        )
        rest_local = parent_rest.transposed() @ rig_rest
        desired_local = parent_pose.transposed() @ desired_rig_basis
        local_delta = rest_local.transposed() @ desired_local

    basis = local_delta.to_4x4()
    basis.translation = pose_bone.matrix_basis.translation.copy()
    pose_bone.matrix_basis = basis
    bpy.context.view_layer.update()


def canonical_parent_and_rest_local(
    armature: bpy.types.Object,
    canonical: dict,
    canonical_name: str,
) -> tuple[Matrix, Matrix]:
    bone = canonical["canonical_bones"][canonical_name]
    parent_name = bone["parent"]
    if parent_name is None:
        raise RuntimeError(
            f"{canonical_name}: ankle solve requires a parent bone."
        )

    parent_bone = canonical["canonical_bones"][parent_name]
    parent_pose_bone = armature.pose.bones[parent_bone["rig_bone"]]
    parent_canonical_pose = canonical_basis_from_rig_pose(
        parent_pose_bone,
        parent_bone,
    )

    parent_rest = matrix3(
        parent_bone["canonical_rest_contract"]["basis_armature_local"]
    )
    canonical_rest = matrix3(
        bone["canonical_rest_contract"]["basis_armature_local"]
    )
    rest_local = parent_rest.transposed() @ canonical_rest
    return parent_canonical_pose, rest_local


def ankle_delta_matrix(
    plantar_dorsiflexion: float,
    inversion_eversion: float,
    side: str,
) -> Matrix:
    side_sign = 1.0 if side == "left" else -1.0
    plantar_angle = math.radians(-float(plantar_dorsiflexion))
    inversion_angle = math.radians(
        side_sign * float(inversion_eversion)
    )

    cx = math.cos(plantar_angle)
    sx = math.sin(plantar_angle)
    cy = math.cos(inversion_angle)
    sy = math.sin(inversion_angle)

    rx = Matrix(
        (
            (1.0, 0.0, 0.0),
            (0.0, cx, -sx),
            (0.0, sx, cx),
        )
    )
    ry = Matrix(
        (
            (cy, 0.0, sy),
            (0.0, 1.0, 0.0),
            (-sy, 0.0, cy),
        )
    )
    return rx @ ry


def canonical_foot_basis_from_ankle_dofs(
    parent_canonical_pose: Matrix,
    rest_local: Matrix,
    plantar_dorsiflexion: float,
    inversion_eversion: float,
    side: str,
) -> Matrix:
    return (
        parent_canonical_pose
        @ rest_local
        @ ankle_delta_matrix(
            plantar_dorsiflexion,
            inversion_eversion,
            side,
        )
    )


def solve_preferred_ankle_flat_contact(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    canonical_name: str,
    side: str,
    up_axis: Vector,
    minimum_up_alignment_dot: float,
) -> dict:
    parent_pose, rest_local = canonical_parent_and_rest_local(
        armature,
        canonical,
        canonical_name,
    )

    limits = constraints["joint_limits"]["ankle_2dof"]["dofs"]
    plantar_pref = limits["plantar_dorsiflexion"]["preferred"]
    inversion_pref = limits["inversion_eversion"]["preferred"]

    current_bone = canonical["canonical_bones"][canonical_name]
    current_pose_bone = armature.pose.bones[current_bone["rig_bone"]]
    current_canonical = canonical_basis_from_rig_pose(
        current_pose_bone,
        current_bone,
    )
    current_y = Vector(
        (
            current_canonical[0][1],
            current_canonical[1][1],
            current_canonical[2][1],
        )
    )
    current_heading = current_y - up_axis * current_y.dot(up_axis)
    if current_heading.length > 1e-8:
        current_heading.normalize()
    else:
        current_heading = None

    def evaluate(plantar: float, inversion: float) -> tuple:
        basis = canonical_foot_basis_from_ankle_dofs(
            parent_pose,
            rest_local,
            plantar,
            inversion,
            side,
        )
        z_axis = Vector(
            (basis[0][2], basis[1][2], basis[2][2])
        ).normalized()
        up_dot = max(-1.0, min(1.0, z_axis.dot(up_axis)))
        tilt_error = 1.0 - up_dot

        heading_error = 0.0
        if current_heading is not None:
            y_axis = Vector(
                (basis[0][1], basis[1][1], basis[2][1])
            )
            projected = y_axis - up_axis * y_axis.dot(up_axis)
            if projected.length > 1e-8:
                projected.normalize()
                heading_error = 1.0 - max(
                    -1.0,
                    min(1.0, projected.dot(current_heading)),
                )
            else:
                heading_error = 2.0

        magnitude = abs(plantar) + abs(inversion)
        return (
            tilt_error,
            heading_error,
            magnitude,
            plantar,
            inversion,
            basis,
            up_dot,
        )

    pmin = float(plantar_pref["min"])
    pmax = float(plantar_pref["max"])
    imin = float(inversion_pref["min"])
    imax = float(inversion_pref["max"])

    best = None

    def consider(plantar: float, inversion: float) -> None:
        nonlocal best
        if not pmin <= plantar <= pmax:
            return
        if not imin <= inversion <= imax:
            return
        candidate = evaluate(plantar, inversion)
        key = candidate[:5]
        if best is None or key < best[:5]:
            best = candidate

    # Coarse preferred-envelope search.
    plantar = pmin
    while plantar <= pmax + 1e-9:
        inversion = imin
        while inversion <= imax + 1e-9:
            consider(plantar, inversion)
            inversion += 1.0
        plantar += 1.0

    if best is None:
        raise RuntimeError("No preferred ankle candidate exists.")

    # Deterministic local refinement around the best candidate.
    for step in (0.1, 0.01, 0.001):
        center_p = float(best[3])
        center_i = float(best[4])
        for p_offset in range(-10, 11):
            for i_offset in range(-10, 11):
                consider(
                    center_p + p_offset * step,
                    center_i + i_offset * step,
                )

    tilt_error, heading_error, _magnitude, plantar, inversion, basis, up_dot = best

    if up_dot < float(minimum_up_alignment_dot):
        raise RuntimeError(
            f"{canonical_name}: preferred ankle envelope cannot flatten "
            f"foot. up_dot={up_dot:.10f} < "
            f"{float(minimum_up_alignment_dot):.10f}; "
            f"best plantar={plantar:.6f}, inversion={inversion:.6f}."
        )

    return {
        "basis": basis,
        "plantar_dorsiflexion": float(plantar),
        "inversion_eversion": float(inversion),
        "up_alignment_dot": float(up_dot),
        "tilt_error": float(tilt_error),
        "heading_error": float(heading_error),
    }


def realize_full_foot_orientation(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    retarget_axis_contract: dict,
    up_axis: Vector,
    minimum_up_alignment_dot: float,
) -> dict:
    ankle_ops = retarget_axis_contract["lower_body_joint_axes"]["ankle_2dof"]
    expected = [
        ("plantar_dorsiflexion", "X", -1.0, False),
        ("inversion_eversion", "Y", 1.0, True),
    ]
    actual = [
        (
            item.get("dof"),
            item["axis"],
            float(item["scale"]),
            bool(item["side_sign"]),
        )
        for item in ankle_ops
    ]
    if actual != expected:
        raise RuntimeError(
            f"Unexpected ankle axis contract for contact solve: {actual}."
        )

    evidence = {}
    for side in ("left", "right"):
        canonical_name = f"{side}_foot"
        bone = canonical["canonical_bones"][canonical_name]
        rig_name = bone["rig_bone"]
        pose_bone = armature.pose.bones[rig_name]

        solution = solve_preferred_ankle_flat_contact(
            armature,
            canonical,
            constraints,
            canonical_name,
            side,
            up_axis,
            minimum_up_alignment_dot,
        )
        desired_canonical = solution["basis"]

        desired_rig = rig_basis_from_canonical_pose(
            bone,
            desired_canonical,
        )
        apply_absolute_rig_rotation_via_matrix_basis(
            armature,
            rig_name,
            desired_rig,
        )

        actual_canonical = canonical_basis_from_rig_pose(
            armature.pose.bones[rig_name],
            bone,
        )
        alignment_error = matrix_max_error(
            actual_canonical,
            desired_canonical,
        )
        if alignment_error > 0.00005:
            raise RuntimeError(
                f"{canonical_name}: contact-frame application error "
                f"{alignment_error}."
            )

        evidence[side] = {
            "rig_bone": rig_name,
            "plantar_dorsiflexion_deg": round(
                float(solution["plantar_dorsiflexion"]),
                8,
            ),
            "inversion_eversion_deg": round(
                float(solution["inversion_eversion"]),
                8,
            ),
            "up_alignment_dot": round(
                float(solution["up_alignment_dot"]),
                10,
            ),
            "tilt_error": round(
                float(solution["tilt_error"]),
                10,
            ),
            "heading_error": round(
                float(solution["heading_error"]),
                10,
            ),
            "contact_frame_application_error": round(
                float(alignment_error),
                10,
            ),
            "preferred_envelope": "PASS",
        }

    return evidence


def set_root_translation_armature_space(
    armature: bpy.types.Object,
    root_name: str,
    desired_translation: Vector,
) -> None:
    pose_bone = armature.pose.bones[root_name]
    basis = pose_bone.matrix_basis.copy()
    rest_basis = armature.data.bones[root_name].matrix_local.to_3x3().normalized()
    local_translation = rest_basis.transposed() @ desired_translation
    basis.translation = local_translation
    pose_bone.matrix_basis = basis
    bpy.context.view_layer.update()


def rotation_application_errors(
    armature: bpy.types.Object,
    pose_entry: dict,
) -> dict:
    local_max = 0.0
    absolute_max = 0.0
    per_bone = {}

    for canonical_name, target in pose_entry["rig_pose"].items():
        rig_name = target["rig_bone"]
        pose_bone = armature.pose.bones[rig_name]
        local_actual = normalized_basis(pose_bone.matrix_basis)
        local_target = matrix3(target["local_pose_delta_matrix"])
        absolute_actual = normalized_basis(pose_bone.matrix)
        absolute_target = matrix3(target["armature_basis"])

        local_error = matrix_max_error(local_actual, local_target)
        absolute_error = matrix_max_error(absolute_actual, absolute_target)
        local_max = max(local_max, local_error)
        absolute_max = max(absolute_max, absolute_error)
        per_bone[canonical_name] = {
            "rig_bone": rig_name,
            "local_rotation_error": round(local_error, 10),
            "absolute_rotation_error": round(absolute_error, 10),
        }

    return {
        "max_local_rotation_error": round(local_max, 10),
        "max_absolute_rotation_error": round(absolute_max, 10),
        "per_bone": per_bone,
    }


def extract_exact_ankle_inversion(
    canonical_local_delta: Matrix,
    side: str,
) -> float:
    side_sign = 1.0 if side == "left" else -1.0
    value = max(
        -1.0,
        min(1.0, float(canonical_local_delta[0][2])),
    )
    return math.degrees(math.asin(value)) / side_sign


def apply_releve_plantar_candidate(
    armature: bpy.types.Object,
    canonical: dict,
    pose_entry: dict,
    plantar_dorsiflexion: float,
) -> dict:
    evidence = {}
    for side in ("left", "right"):
        canonical_name = f"{side}_foot"
        bone = canonical["canonical_bones"][canonical_name]
        local_delta = matrix3(
            pose_entry["canonical_pose"][canonical_name][
                "local_pose_delta_matrix"
            ]
        )
        inversion = extract_exact_ankle_inversion(
            local_delta,
            side,
        )
        parent_pose, rest_local = canonical_parent_and_rest_local(
            armature,
            canonical,
            canonical_name,
        )
        desired_canonical = canonical_foot_basis_from_ankle_dofs(
            parent_pose,
            rest_local,
            plantar_dorsiflexion,
            inversion,
            side,
        )
        desired_rig = rig_basis_from_canonical_pose(
            bone,
            desired_canonical,
        )
        apply_absolute_rig_rotation_via_matrix_basis(
            armature,
            bone["rig_bone"],
            desired_rig,
        )
        evidence[side] = {
            "rig_bone": bone["rig_bone"],
            "plantar_dorsiflexion_deg": round(
                float(plantar_dorsiflexion),
                8,
            ),
            "inversion_eversion_deg": round(
                float(inversion),
                8,
            ),
        }
    return evidence


def candidate_releve_geometry(
    armature: bpy.types.Object,
    anchors: dict,
    rest_heights: dict,
    up_axis: Vector,
    low_height_quantile: float,
) -> dict:
    posed = contact_heights(
        armature,
        anchors,
        up_axis,
        low_height_quantile,
    )
    shift = root_shift_for_contact(
        "SOLVE_FOREFOOT_CONTACT",
        rest_heights,
        posed,
    )

    heel_lifts = {
        side: (
            float(posed[side]["rear"])
            + float(shift)
            - float(rest_heights[side]["rear"])
        )
        for side in ("left", "right")
    }
    fore_errors = {
        side: (
            float(posed[side]["fore"])
            + float(shift)
            - float(rest_heights[side]["fore"])
        )
        for side in ("left", "right")
    }
    return {
        "root_shift": float(shift),
        "heel_lifts": heel_lifts,
        "fore_errors": fore_errors,
        "max_fore_error": max(
            abs(value)
            for value in fore_errors.values()
        ),
    }


def solve_releve_plantar_for_mesh_heel_height(
    armature: bpy.types.Object,
    canonical: dict,
    pose_entry: dict,
    constraints: dict,
    anchors: dict,
    rest_heights: dict,
    up_axis: Vector,
    low_height_quantile: float,
    target_heights: dict,
    coarse_step_deg: float,
    refine_steps_deg: list[float],
) -> dict:
    preferred = constraints["joint_limits"]["ankle_2dof"]["dofs"][
        "plantar_dorsiflexion"
    ]["preferred"]
    minimum = float(preferred["min"])
    maximum = float(preferred["max"])

    best = None

    def evaluate(plantar: float) -> None:
        nonlocal best
        if not minimum <= plantar <= maximum:
            return
        apply_rotation_deltas(armature, pose_entry)
        application = apply_releve_plantar_candidate(
            armature,
            canonical,
            pose_entry,
            plantar,
        )
        geometry = candidate_releve_geometry(
            armature,
            anchors,
            rest_heights,
            up_axis,
            low_height_quantile,
        )
        heel_errors = {
            side: abs(
                float(geometry["heel_lifts"][side])
                - float(target_heights[side])
            )
            for side in ("left", "right")
        }
        maximum_heel_error = max(heel_errors.values())
        bilateral_error = abs(
            float(geometry["heel_lifts"]["left"])
            - float(geometry["heel_lifts"]["right"])
        )
        key = (
            maximum_heel_error,
            float(geometry["max_fore_error"]),
            bilateral_error,
            abs(float(plantar)),
        )
        candidate = {
            "key": key,
            "plantar_dorsiflexion_deg": float(plantar),
            "application": application,
            "geometry": geometry,
            "heel_errors": heel_errors,
        }
        if best is None or key < best["key"]:
            best = candidate

    step = float(coarse_step_deg)
    plantar = minimum
    while plantar <= maximum + 1e-9:
        evaluate(plantar)
        plantar += step

    if best is None:
        raise RuntimeError(
            "Releve plantar solver found no preferred candidate."
        )

    for refine_step in refine_steps_deg:
        center = float(best["plantar_dorsiflexion_deg"])
        for offset in range(-10, 11):
            evaluate(
                center + offset * float(refine_step)
            )

    # Re-apply the winning candidate so Blender is left in solved state.
    apply_rotation_deltas(armature, pose_entry)
    application = apply_releve_plantar_candidate(
        armature,
        canonical,
        pose_entry,
        float(best["plantar_dorsiflexion_deg"]),
    )
    geometry = candidate_releve_geometry(
        armature,
        anchors,
        rest_heights,
        up_axis,
        low_height_quantile,
    )

    return {
        "plantar_dorsiflexion_deg": float(
            best["plantar_dorsiflexion_deg"]
        ),
        "application": application,
        "geometry": geometry,
        "heel_errors": {
            side: abs(
                float(geometry["heel_lifts"][side])
                - float(target_heights[side])
            )
            for side in ("left", "right")
        },
        "preferred_envelope": {
            "min": minimum,
            "max": maximum,
        },
    }


def root_shift_for_contact(
    mode: str,
    rest_heights: dict,
    posed_heights: dict,
) -> float:
    if mode == "KEEP_REST":
        return 0.0

    regions = (
        ("rear", "fore")
        if mode == "SOLVE_FULL_FOOT_CONTACT"
        else ("fore",)
    )
    shifts = []
    for side in ("left", "right"):
        for region in regions:
            shifts.append(
                float(rest_heights[side][region])
                - float(posed_heights[side][region])
            )
    return median(shifts)


def contact_errors(
    mode: str,
    rest_heights: dict,
    posed_heights: dict,
) -> dict:
    if mode == "KEEP_REST":
        return {"required": False, "errors": {}}

    regions = (
        ("rear", "fore")
        if mode == "SOLVE_FULL_FOOT_CONTACT"
        else ("fore",)
    )
    errors = {}
    maximum = 0.0
    for side in ("left", "right"):
        errors[side] = {}
        for region in regions:
            error = (
                float(posed_heights[side][region])
                - float(rest_heights[side][region])
            )
            errors[side][region] = round(error, 8)
            maximum = max(maximum, abs(error))
    return {
        "required": True,
        "max_abs_error": round(maximum, 8),
        "errors": errors,
    }


def body_metrics(canonical: dict) -> dict:
    bones = canonical["canonical_bones"]
    foot_length = sum(
        (
            float(bones["left_foot"]["length"]),
            float(bones["left_toes"]["length"]),
            float(bones["right_foot"]["length"]),
            float(bones["right_toes"]["length"]),
        )
    ) / 2.0
    leg_length = sum(
        (
            float(bones["left_thigh"]["length"]),
            float(bones["left_shin"]["length"]),
            float(bones["left_foot"]["length"]),
            float(bones["right_thigh"]["length"]),
            float(bones["right_shin"]["length"]),
            float(bones["right_foot"]["length"]),
        )
    ) / 2.0
    return {
        "foot_chain_length": foot_length,
        "leg_chain_length": leg_length,
    }


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    canonical_path = Path(args.canonical_profile).resolve()
    retarget_path = Path(args.retarget_profile).resolve()
    constraint_path = Path(args.constraint_profile).resolve()
    axis_contract_path = Path(args.retarget_axis_contract).resolve()
    contract_path = Path(args.contract).resolve()
    output_path = Path(args.output).resolve()

    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    retarget = json.loads(retarget_path.read_text(encoding="utf-8"))
    constraints = json.loads(constraint_path.read_text(encoding="utf-8"))
    retarget_axis_contract = json.loads(
        axis_contract_path.read_text(encoding="utf-8")
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    require(canonical["phase"] == "10.6.2", "Requires Phase 10.6.2 canonical profile.")
    require(retarget["phase"] == "10.6.6", "Requires Phase 10.6.6 retarget profile.")
    require(constraints["phase"] == "10.6.3", "Requires Phase 10.6.3 constraints.")
    require(
        retarget_axis_contract["phase"] == "10.6.6",
        "Requires Phase 10.6.6 retarget axis contract.",
    )
    require(contract["phase"] == PHASE, "Static application contract phase mismatch.")
    require(retarget["gate"]["orientation_retarget_pass"], "10.6.6 retarget gate not passed.")
    require(
        retarget["inputs"]["source_glb_sha256"] == canonical["source"]["sha256"],
        "Retarget/source SHA binding mismatch.",
    )

    source_glb = repo / canonical["source"]["path"]
    require(source_glb.exists(), f"Source GLB missing: {source_glb}")
    require(
        sha256_file(source_glb) == canonical["source"]["sha256"],
        "Source GLB changed after calibration.",
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(source_glb))
    require("FINISHED" in result, f"glTF import failed: {result}")

    armature = find_armature(canonical["source"]["armature"])
    if armature.animation_data is not None:
        armature.animation_data_clear()
    for obj in bpy.context.scene.objects:
        if obj.animation_data is not None:
            obj.animation_data_clear()

    all_rig_names = {
        bone["rig_bone"]
        for bone in canonical["canonical_bones"].values()
    }
    missing = sorted(all_rig_names - set(armature.pose.bones.keys()))
    require(not missing, f"Imported rig missing calibrated bones: {missing}")

    frame = canonical["body_frame"]["declared_axes_armature_local"]
    up_axis = Vector(frame["up"]).normalized()
    front_axis = Vector(frame["front"]).normalized()

    foot_groups = {
        "left": {
            canonical["canonical_bones"]["left_foot"]["rig_bone"],
            canonical["canonical_bones"]["left_toes"]["rig_bone"],
        },
        "right": {
            canonical["canonical_bones"]["right_foot"]["rig_bone"],
            canonical["canonical_bones"]["right_toes"]["rig_bone"],
        },
    }
    required_groups = set().union(*foot_groups.values())
    meshes = relevant_mesh_objects(armature, required_groups)

    sampling = contract["contact_sampling"]
    anchors = {}
    for side in ("left", "right"):
        samples = collect_weighted_samples(
            meshes,
            foot_groups[side],
            float(sampling["minimum_vertex_group_weight"]),
        )
        anchors[side] = classify_contact_samples(
            armature,
            samples,
            front_axis,
            float(sampling["rear_fraction"]),
            float(sampling["fore_fraction"]),
        )

    clear_pose(armature)
    rest_heights = contact_heights(
        armature,
        anchors,
        up_axis,
        float(sampling["low_height_quantile"]),
    )

    metrics = body_metrics(canonical)
    thresholds = contract["proof_thresholds"]
    contact_tolerance = (
        metrics["foot_chain_length"]
        * float(thresholds["contact_error_max_foot_length_fraction"])
    )
    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]

    pose_reports = {}
    for pose_name in ("bras_bas", "en_avant", "second", "fifth", "plie", "releve"):
        pose_entry = retarget["poses"][pose_name]
        require(
            len(pose_entry["rig_pose"]) == 24,
            f"{pose_name}: expected 24 rig rotations, got "
            f"{len(pose_entry['rig_pose'])}.",
        )
        apply_rotation_deltas(armature, pose_entry)
        rotation_errors = rotation_application_errors(
            armature,
            pose_entry,
        )

        require(
            rotation_errors["max_local_rotation_error"]
            <= float(thresholds["local_rotation_matrix_error_max"]),
            f"{pose_name}: local matrix application error "
            f"{rotation_errors['max_local_rotation_error']}.",
        )
        require(
            rotation_errors["max_absolute_rotation_error"]
            <= float(thresholds["absolute_rotation_matrix_error_max"]),
            f"{pose_name}: absolute matrix application error "
            f"{rotation_errors['max_absolute_rotation_error']}.",
        )

        mode = contract["root_translation_modes"][pose_name]
        contact_orientation = {}
        releve_realization = {}
        if mode == "SOLVE_FULL_FOOT_CONTACT":
            contact_orientation = realize_full_foot_orientation(
                armature,
                canonical,
                constraints,
                retarget_axis_contract,
                up_axis,
                float(
                    thresholds[
                        "full_foot_up_alignment_min_dot"
                    ]
                ),
            )

        non_rot = pose_entry.get("non_rotational_pose_contract", {})
        scalars = non_rot.get("translation_contact_scalars", {})

        if pose_name == "releve":
            target_heights = {
                "left": float(scalars["left_heel_height"]),
                "right": float(scalars["right_heel_height"]),
            }
            releve_realization = solve_releve_plantar_for_mesh_heel_height(
                armature,
                canonical,
                pose_entry,
                constraints,
                anchors,
                rest_heights,
                up_axis,
                float(sampling["low_height_quantile"]),
                target_heights,
                float(
                    thresholds[
                        "releve_plantar_search_coarse_step_deg"
                    ]
                ),
                [
                    float(value)
                    for value in thresholds[
                        "releve_plantar_search_refine_steps_deg"
                    ]
                ],
            )

        before_heights = contact_heights(
            armature,
            anchors,
            up_axis,
            float(sampling["low_height_quantile"]),
        )
        shift = root_shift_for_contact(
            mode,
            rest_heights,
            before_heights,
        )
        desired_translation = up_axis * shift
        set_root_translation_armature_space(
            armature,
            root_name,
            desired_translation,
        )

        after_heights = contact_heights(
            armature,
            anchors,
            up_axis,
            float(sampling["low_height_quantile"]),
        )
        proof = contact_errors(
            mode,
            rest_heights,
            after_heights,
        )
        if proof["required"]:
            require(
                proof["max_abs_error"] <= contact_tolerance,
                f"{pose_name}: contact error {proof['max_abs_error']} "
                f"> tolerance {contact_tolerance}.",
            )

        consistency = {}

        if pose_name == "fifth":
            max_shift = (
                metrics["leg_chain_length"]
                * float(
                    thresholds[
                        "fifth_root_shift_max_leg_length_fraction"
                    ]
                )
            )
            require(
                abs(shift) <= max_shift,
                f"fifth: root shift {shift} exceeds {max_shift}.",
            )
            consistency["root_shift_near_standing"] = True

        if pose_name == "plie":
            target_descent = float(scalars["pelvis_descent"])
            actual_descent = -float(shift)
            absolute_error = abs(actual_descent - target_descent)
            allowed = max(
                target_descent
                * float(
                    thresholds["plie_descent_relative_error_max"]
                ),
                metrics["leg_chain_length"]
                * float(
                    thresholds[
                        "plie_descent_absolute_leg_fraction_max"
                    ]
                ),
            )
            require(
                actual_descent > 0.0,
                f"plie: contact solve did not lower pelvis ({actual_descent}).",
            )
            require(
                absolute_error <= allowed,
                f"plie: pelvis descent error {absolute_error} > {allowed}.",
            )
            consistency.update(
                {
                    "target_pelvis_descent": round(target_descent, 8),
                    "actual_contact_solved_descent": round(
                        actual_descent,
                        8,
                    ),
                    "absolute_error": round(absolute_error, 8),
                    "allowed_error": round(allowed, 8),
                }
            )

        if pose_name == "releve":
            target_left = float(scalars["left_heel_height"])
            target_right = float(scalars["right_heel_height"])
            heel_lifts = {
                side: (
                    float(after_heights[side]["rear"])
                    - float(rest_heights[side]["rear"])
                )
                for side in ("left", "right")
            }
            preferred = releve_realization["preferred_envelope"]
            selected_plantar = float(
                releve_realization["plantar_dorsiflexion_deg"]
            )
            require(
                float(preferred["min"])
                <= selected_plantar
                <= float(preferred["max"]),
                "releve: plantar solver left preferred envelope.",
            )
            minimum_lift = (
                metrics["foot_chain_length"]
                * float(
                    thresholds[
                        "releve_heel_must_rise_min_foot_fraction"
                    ]
                )
            )
            for side, target in (
                ("left", target_left),
                ("right", target_right),
            ):
                actual = heel_lifts[side]
                allowed = max(
                    target
                    * float(
                        thresholds[
                            "releve_heel_lift_relative_error_max"
                        ]
                    ),
                    metrics["foot_chain_length"]
                    * float(
                        thresholds[
                            "releve_heel_lift_absolute_foot_fraction_max"
                        ]
                    ),
                )
                require(
                    actual >= minimum_lift,
                    f"releve: {side} heel did not rise enough "
                    f"({actual} < {minimum_lift}).",
                )
                require(
                    abs(actual - target) <= allowed,
                    f"releve: {side} heel lift error "
                    f"{abs(actual - target)} > {allowed}.",
                )
            consistency["heel_lift"] = {
                side: round(value, 8)
                for side, value in heel_lifts.items()
            }
            consistency["target_heel_height"] = {
                "left": round(target_left, 8),
                "right": round(target_right, 8),
            }
            consistency["solved_plantar_dorsiflexion_deg"] = round(
                selected_plantar,
                8,
            )
            consistency["plantar_preferred_envelope"] = preferred

        pose_reports[pose_name] = {
            "root_translation_mode": mode,
            "root_translation_armature_local": [
                round(float(value), 8)
                for value in desired_translation
            ],
            "root_up_shift": round(float(shift), 8),
            "rotation_application": rotation_errors,
            "contact_orientation_realization": contact_orientation,
            "releve_contact_realization": releve_realization,
            "contact_proof": proof,
            "contact_consistency": consistency,
            "blender_pose_applied": True,
            "rendered": False,
        }

    output = {
        "phase": PHASE,
        "schema_version": contract["schema_version"],
        "proof_id": contract["contract_id"],
        "source": {
            "path": canonical["source"]["path"],
            "sha256": canonical["source"]["sha256"],
            "armature": armature.name,
        },
        "policy": contract["policy"],
        "mesh_contact_sampling": {
            "mesh_objects": [obj.name for obj in meshes],
            "vertex_group_names": {
                side: sorted(groups)
                for side, groups in foot_groups.items()
            },
            "anchor_counts": {
                side: {
                    region: len(samples)
                    for region, samples in regions.items()
                }
                for side, regions in anchors.items()
            },
            "rest_anchor_heights": rest_heights,
            "contact_tolerance": round(contact_tolerance, 8),
        },
        "body_metrics": {
            key: round(value, 8)
            for key, value in metrics.items()
        },
        "poses": pose_reports,
        "gate": {
            "pose_count": len(pose_reports),
            "all_24_bone_rotations_applied": True,
            "local_matrix_application_pass": True,
            "absolute_matrix_application_pass": True,
            "full_foot_orientation_realization_pass": True,
            "full_foot_contact_pass": True,
            "forefoot_contact_pass": True,
            "plie_root_descent_consistency_pass": True,
            "releve_plantar_contact_realization_pass": True,
            "releve_heel_lift_consistency_pass": True,
            "blender_application_performed": True,
            "render_performed": False,
            "animation_performed": False,
            "glb_exported": False,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")

    print("PHASE10_6_7_STATIC_RIG_APPLICATION=PASS")
    print(f"REPORT={output_path}")
    print("POSES=6/6")
    print("ROTATION_APPLICATION=PASS")
    print("FULL_FOOT_ORIENTATION=PASS")
    print("FULL_FOOT_CONTACT=PASS")
    print("FOREFOOT_CONTACT=PASS")
    print("PLIE_ROOT_DESCENT=PASS")
    print("RELEVE_PLANTAR_CONTACT_REALIZATION=PASS")
    print("RELEVE_HEEL_LIFT=PASS")
    print("BLENDER_APPLICATION=PERFORMED")
    print("RENDER=NOT_PERFORMED")
    print("GLB_EXPORT=NOT_PERFORMED")


if __name__ == "__main__":
    main()
