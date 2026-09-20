"""Phase 10.6.7 static rig application + contact/root translation proof.

This is the first Phase 10.6 step that applies solved transforms to the
actual imported low_poly_girl armature. It does not render or export.
"""

from __future__ import annotations

import argparse
import copy
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
    parser.add_argument("--grammar-profile", required=True)
    parser.add_argument("--intent-spec", required=True)
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
            "No deformed mesh object contains required vertex groups."
        )
    return meshes


def rig_bone_subtree_names(
    armature: bpy.types.Object,
    root_bone_name: str,
) -> set[str]:
    root = armature.data.bones.get(root_bone_name)
    if root is None:
        raise RuntimeError(
            f"Rig bone subtree root missing: {root_bone_name}."
        )

    names: set[str] = set()
    stack = [root]
    while stack:
        bone = stack.pop()
        if bone.name in names:
            continue
        names.add(bone.name)
        stack.extend(list(bone.children))
    return names


def hand_rig_vertex_groups(
    armature: bpy.types.Object,
    canonical: dict,
) -> dict[str, set[str]]:
    groups = {}
    for side in ("left", "right"):
        hand_root = canonical["canonical_bones"][
            f"{side}_hand"
        ]["rig_bone"]
        groups[side] = rig_bone_subtree_names(
            armature,
            hand_root,
        )
    return groups


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
            f"No vertices meet vertex-group weight threshold for {sorted(group_names)}."
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
    anchors: dict,
    rest_heights: dict,
    low_height_quantile: float,
    minimum_seed_up_alignment_dot: float,
    coarse_step_deg: float,
    refine_steps_deg: list[float],
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

    def basis_metrics(plantar: float, inversion: float) -> dict:
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

        return {
            "basis": basis,
            "up_dot": float(up_dot),
            "tilt_error": float(1.0 - up_dot),
            "heading_error": float(heading_error),
        }

    pmin = float(plantar_pref["min"])
    pmax = float(plantar_pref["max"])
    imin = float(inversion_pref["min"])
    imax = float(inversion_pref["max"])

    # Stage 1: find the canonical preferred-envelope seed. This preserves the
    # old anatomical rule that a valid foot-up solution must exist before any
    # mesh-specific correction is allowed.
    seed = None

    def consider_seed(plantar: float, inversion: float) -> None:
        nonlocal seed
        if not pmin <= plantar <= pmax:
            return
        if not imin <= inversion <= imax:
            return
        metrics = basis_metrics(plantar, inversion)
        key = (
            metrics["tilt_error"],
            metrics["heading_error"],
            abs(plantar) + abs(inversion),
            plantar,
            inversion,
        )
        candidate = {
            "key": key,
            "plantar": float(plantar),
            "inversion": float(inversion),
            **metrics,
        }
        if seed is None or key < seed["key"]:
            seed = candidate

    plantar = pmin
    while plantar <= pmax + 1e-9:
        inversion = imin
        while inversion <= imax + 1e-9:
            consider_seed(plantar, inversion)
            inversion += 1.0
        plantar += 1.0

    if seed is None:
        raise RuntimeError("No preferred ankle seed exists.")

    for step in (0.1, 0.01, 0.001):
        center_p = float(seed["plantar"])
        center_i = float(seed["inversion"])
        for p_offset in range(-10, 11):
            for i_offset in range(-10, 11):
                consider_seed(
                    center_p + p_offset * step,
                    center_i + i_offset * step,
                )

    if seed["up_dot"] < float(minimum_seed_up_alignment_dot):
        raise RuntimeError(
            f"{canonical_name}: preferred ankle seed cannot align foot-up. "
            f"up_dot={seed['up_dot']:.10f} < "
            f"{float(minimum_seed_up_alignment_dot):.10f}."
        )

    # Stage 2: keep the seed inversion and solve plantar against the actual
    # deformed rear/fore mesh contact plane. A single root translation can
    # only satisfy full-foot contact when rear and fore require the same
    # vertical shift, so minimize that shift mismatch directly.
    best = None

    def consider_mesh(plantar: float) -> None:
        nonlocal best
        if not pmin <= plantar <= pmax:
            return
        inversion = float(seed["inversion"])
        metrics = basis_metrics(plantar, inversion)

        desired_rig = rig_basis_from_canonical_pose(
            current_bone,
            metrics["basis"],
        )
        apply_absolute_rig_rotation_via_matrix_basis(
            armature,
            current_bone["rig_bone"],
            desired_rig,
        )

        posed = {
            region: anchor_height(
                armature,
                anchors[side][region],
                up_axis,
                low_height_quantile,
            )
            for region in ("rear", "fore")
        }
        required_shifts = {
            region: (
                float(rest_heights[side][region])
                - float(posed[region])
            )
            for region in ("rear", "fore")
        }
        mesh_flatness_error = abs(
            required_shifts["rear"] - required_shifts["fore"]
        )
        key = (
            mesh_flatness_error,
            metrics["tilt_error"],
            metrics["heading_error"],
            abs(float(plantar) - float(seed["plantar"])),
            abs(float(plantar)),
        )
        candidate = {
            "key": key,
            "plantar": float(plantar),
            "inversion": inversion,
            "posed_heights": posed,
            "required_shifts": required_shifts,
            "mesh_flatness_error": float(mesh_flatness_error),
            **metrics,
        }
        if best is None or key < best["key"]:
            best = candidate

    step = float(coarse_step_deg)
    plantar = pmin
    while plantar <= pmax + 1e-9:
        consider_mesh(plantar)
        plantar += step

    if best is None:
        raise RuntimeError(
            f"{canonical_name}: no mesh-contact ankle candidate remains "
            "inside the preferred ankle envelope."
        )

    for step in refine_steps_deg:
        center = float(best["plantar"])
        for offset in range(-10, 11):
            consider_mesh(center + offset * float(step))

    # Leave Blender in the winning mesh-contact state.
    desired_rig = rig_basis_from_canonical_pose(
        current_bone,
        best["basis"],
    )
    apply_absolute_rig_rotation_via_matrix_basis(
        armature,
        current_bone["rig_bone"],
        desired_rig,
    )

    return {
        "basis": best["basis"],
        "plantar_dorsiflexion": float(best["plantar"]),
        "inversion_eversion": float(best["inversion"]),
        "up_alignment_dot": float(best["up_dot"]),
        "tilt_error": float(best["tilt_error"]),
        "heading_error": float(best["heading_error"]),
        "mesh_flatness_error": float(best["mesh_flatness_error"]),
        "rear_required_shift": float(
            best["required_shifts"]["rear"]
        ),
        "fore_required_shift": float(
            best["required_shifts"]["fore"]
        ),
        "canonical_seed": {
            "plantar_dorsiflexion": float(seed["plantar"]),
            "inversion_eversion": float(seed["inversion"]),
            "up_alignment_dot": float(seed["up_dot"]),
        },
    }


def realize_full_foot_orientation(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    retarget_axis_contract: dict,
    up_axis: Vector,
    anchors: dict,
    rest_heights: dict,
    low_height_quantile: float,
    minimum_seed_up_alignment_dot: float,
    coarse_step_deg: float,
    refine_steps_deg: list[float],
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

        solution = solve_preferred_ankle_flat_contact(
            armature,
            canonical,
            constraints,
            canonical_name,
            side,
            up_axis,
            anchors,
            rest_heights,
            low_height_quantile,
            minimum_seed_up_alignment_dot,
            coarse_step_deg,
            refine_steps_deg,
        )
        desired_canonical = solution["basis"]

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
            "mesh_flatness_error": round(
                float(solution["mesh_flatness_error"]),
                10,
            ),
            "rear_required_shift": round(
                float(solution["rear_required_shift"]),
                10,
            ),
            "fore_required_shift": round(
                float(solution["fore_required_shift"]),
                10,
            ),
            "canonical_seed": {
                key: round(float(value), 10)
                for key, value in solution["canonical_seed"].items()
            },
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


def extract_exact_ankle_plantar(
    canonical_local_delta: Matrix,
) -> float:
    value = max(
        -1.0,
        min(1.0, float(canonical_local_delta[2][1])),
    )
    return -math.degrees(math.asin(value))


def extract_exact_toe_flexion(
    canonical_local_delta: Matrix,
) -> float:
    value = max(
        -1.0,
        min(1.0, float(canonical_local_delta[2][1])),
    )
    return math.degrees(math.asin(value))


def toe_delta_matrix(toe_flexion: float) -> Matrix:
    angle = math.radians(float(toe_flexion))
    c = math.cos(angle)
    s = math.sin(angle)
    return Matrix(
        (
            (1.0, 0.0, 0.0),
            (0.0, c, -s),
            (0.0, s, c),
        )
    )


def apply_releve_plantar_toe_candidate(
    armature: bpy.types.Object,
    canonical: dict,
    pose_entry: dict,
    plantar_dorsiflexion: float,
    toe_flexion_extension: float,
) -> dict:
    evidence = {}
    for side in ("left", "right"):
        foot_name = f"{side}_foot"
        foot_bone = canonical["canonical_bones"][foot_name]
        foot_local_delta = matrix3(
            pose_entry["canonical_pose"][foot_name][
                "local_pose_delta_matrix"
            ]
        )
        inversion = extract_exact_ankle_inversion(
            foot_local_delta,
            side,
        )
        parent_pose, rest_local = canonical_parent_and_rest_local(
            armature,
            canonical,
            foot_name,
        )
        desired_foot_canonical = canonical_foot_basis_from_ankle_dofs(
            parent_pose,
            rest_local,
            plantar_dorsiflexion,
            inversion,
            side,
        )
        desired_foot_rig = rig_basis_from_canonical_pose(
            foot_bone,
            desired_foot_canonical,
        )
        apply_absolute_rig_rotation_via_matrix_basis(
            armature,
            foot_bone["rig_bone"],
            desired_foot_rig,
        )

        toe_name = f"{side}_toes"
        toe_bone = canonical["canonical_bones"][toe_name]
        foot_pose = canonical_basis_from_rig_pose(
            armature.pose.bones[foot_bone["rig_bone"]],
            foot_bone,
        )
        foot_rest = matrix3(
            foot_bone["canonical_rest_contract"][
                "basis_armature_local"
            ]
        )
        toe_rest = matrix3(
            toe_bone["canonical_rest_contract"][
                "basis_armature_local"
            ]
        )
        toe_rest_local = foot_rest.transposed() @ toe_rest
        desired_toe_canonical = (
            foot_pose
            @ toe_rest_local
            @ toe_delta_matrix(toe_flexion_extension)
        )
        desired_toe_rig = rig_basis_from_canonical_pose(
            toe_bone,
            desired_toe_canonical,
        )
        apply_absolute_rig_rotation_via_matrix_basis(
            armature,
            toe_bone["rig_bone"],
            desired_toe_rig,
        )

        evidence[side] = {
            "foot_rig_bone": foot_bone["rig_bone"],
            "toe_rig_bone": toe_bone["rig_bone"],
            "plantar_dorsiflexion_deg": round(
                float(plantar_dorsiflexion),
                8,
            ),
            "inversion_eversion_deg": round(
                float(inversion),
                8,
            ),
            "toe_flexion_extension_deg": round(
                float(toe_flexion_extension),
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


def solve_releve_plantar_toe_for_mesh_heel_height(
    armature: bpy.types.Object,
    canonical: dict,
    pose_entry: dict,
    constraints: dict,
    anchors: dict,
    rest_heights: dict,
    up_axis: Vector,
    low_height_quantile: float,
    target_heights: dict,
    plantar_coarse_step_deg: float,
    toe_coarse_step_deg: float,
    refine_steps_deg: list[float],
) -> dict:
    ankle_preferred = constraints["joint_limits"]["ankle_2dof"]["dofs"][
        "plantar_dorsiflexion"
    ]["preferred"]
    toe_preferred = constraints["joint_limits"]["mtp_hinge"]["dofs"][
        "toe_flexion_extension"
    ]["preferred"]
    plantar_min = float(ankle_preferred["min"])
    plantar_max = float(ankle_preferred["max"])
    toe_min = float(toe_preferred["min"])
    toe_max = float(toe_preferred["max"])

    semantic_plantar = []
    semantic_toe = []
    for side in ("left", "right"):
        foot_delta = matrix3(
            pose_entry["canonical_pose"][f"{side}_foot"][
                "local_pose_delta_matrix"
            ]
        )
        toe_delta = matrix3(
            pose_entry["canonical_pose"][f"{side}_toes"][
                "local_pose_delta_matrix"
            ]
        )
        semantic_plantar.append(
            extract_exact_ankle_plantar(foot_delta)
        )
        semantic_toe.append(
            extract_exact_toe_flexion(toe_delta)
        )
    semantic_plantar_target = sum(semantic_plantar) / 2.0
    semantic_toe_target = sum(semantic_toe) / 2.0

    best = None

    def evaluate(plantar: float, toe_flexion: float) -> None:
        nonlocal best
        if not plantar_min <= plantar <= plantar_max:
            return
        if not toe_min <= toe_flexion <= toe_max:
            return

        apply_rotation_deltas(armature, pose_entry)
        application = apply_releve_plantar_toe_candidate(
            armature,
            canonical,
            pose_entry,
            plantar,
            toe_flexion,
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
        semantic_deviation = (
            abs(float(plantar) - semantic_plantar_target)
            + abs(float(toe_flexion) - semantic_toe_target)
        )
        key = (
            maximum_heel_error,
            float(geometry["max_fore_error"]),
            bilateral_error,
            semantic_deviation,
            abs(float(plantar)),
            abs(float(toe_flexion)),
        )
        candidate = {
            "key": key,
            "plantar_dorsiflexion_deg": float(plantar),
            "toe_flexion_extension_deg": float(toe_flexion),
            "application": application,
            "geometry": geometry,
            "heel_errors": heel_errors,
        }
        if best is None or key < best["key"]:
            best = candidate

    plantar = plantar_min
    while plantar <= plantar_max + 1e-9:
        toe_flexion = toe_min
        while toe_flexion <= toe_max + 1e-9:
            evaluate(plantar, toe_flexion)
            toe_flexion += float(toe_coarse_step_deg)
        plantar += float(plantar_coarse_step_deg)

    if best is None:
        raise RuntimeError(
            "Releve plantar+toe solver found no preferred candidate."
        )

    for refine_step in refine_steps_deg:
        center_p = float(best["plantar_dorsiflexion_deg"])
        center_t = float(best["toe_flexion_extension_deg"])
        for p_offset in range(-5, 6):
            for t_offset in range(-5, 6):
                evaluate(
                    center_p + p_offset * float(refine_step),
                    center_t + t_offset * float(refine_step),
                )

    # Re-apply the winning candidate so Blender is left in solved state.
    apply_rotation_deltas(armature, pose_entry)
    application = apply_releve_plantar_toe_candidate(
        armature,
        canonical,
        pose_entry,
        float(best["plantar_dorsiflexion_deg"]),
        float(best["toe_flexion_extension_deg"]),
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
        "toe_flexion_extension_deg": float(
            best["toe_flexion_extension_deg"]
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
            "plantar_dorsiflexion": {
                "min": plantar_min,
                "max": plantar_max,
            },
            "toe_flexion_extension": {
                "min": toe_min,
                "max": toe_max,
            },
        },
        "semantic_targets": {
            "plantar_dorsiflexion_deg": float(
                semantic_plantar_target
            ),
            "toe_flexion_extension_deg": float(
                semantic_toe_target
            ),
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


def armature_point_to_body(
    point: Vector,
    canonical: dict,
) -> dict:
    frame = canonical["body_frame"]["declared_axes_armature_local"]
    return {
        "left": float(point.dot(Vector(frame["left"]).normalized())),
        "up": float(point.dot(Vector(frame["up"]).normalized())),
        "front": float(point.dot(Vector(frame["front"]).normalized())),
    }


def realized_middle_fingertip_spacing(
    armature: bpy.types.Object,
    canonical: dict,
    pose_entry: dict,
) -> dict:
    non_rot = pose_entry.get("non_rotational_pose_contract", {})
    contract = non_rot.get("hand_mesh_spacing_contract")
    if contract is None:
        return {"required": False, "status": "NOT_REQUIRED"}

    left_name = canonical["canonical_bones"]["left_middle"]["rig_bone"]
    right_name = canonical["canonical_bones"]["right_middle"]["rig_bone"]
    bpy.context.view_layer.update()
    left_tip = armature_point_to_body(
        Vector(armature.pose.bones[left_name].tail),
        canonical,
    )
    right_tip = armature_point_to_body(
        Vector(armature.pose.bones[right_name].tail),
        canonical,
    )
    gap = float(left_tip["left"]) - float(right_tip["left"])
    minimum = float(contract["minimum_gap"])
    maximum = float(contract["maximum_gap"])
    crossed = gap < 0.0
    return {
        "required": True,
        "status": "DIAGNOSTIC_ONLY",
        "left_middle_rig_bone": left_name,
        "right_middle_rig_bone": right_name,
        "left_middle_tip_body": {
            key: round(value, 8)
            for key, value in left_tip.items()
        },
        "right_middle_tip_body": {
            key: round(value, 8)
            for key, value in right_tip.items()
        },
        "fingertip_gap": round(gap, 8),
        "fingertips_crossed": crossed,
        "minimum_allowed_gap": round(minimum, 8),
        "maximum_allowed_gap": round(maximum, 8),
        "scale_basis": contract["scale_basis"],
    }


def rotation_x(angle_deg: float) -> Matrix:
    angle = math.radians(float(angle_deg))
    c = math.cos(angle)
    s = math.sin(angle)
    return Matrix(
        (
            (1.0, 0.0, 0.0),
            (0.0, c, -s),
            (0.0, s, c),
        )
    )


def rotation_z(angle_deg: float) -> Matrix:
    angle = math.radians(float(angle_deg))
    c = math.cos(angle)
    s = math.sin(angle)
    return Matrix(
        (
            (c, -s, 0.0),
            (s, c, 0.0),
            (0.0, 0.0, 1.0),
        )
    )


def wrist_delta_matrix(
    flexion_extension_deg: float,
    radial_ulnar_deviation_deg: float,
) -> Matrix:
    return (
        rotation_x(flexion_extension_deg)
        @ rotation_z(radial_ulnar_deviation_deg)
    )


def apply_hand_wrist_candidate(
    armature: bpy.types.Object,
    canonical: dict,
    side: str,
    flexion_extension_deg: float,
    radial_ulnar_deviation_deg: float,
) -> None:
    hand_name = f"{side}_hand"
    hand_bone = canonical["canonical_bones"][hand_name]
    parent_pose, rest_local = canonical_parent_and_rest_local(
        armature,
        canonical,
        hand_name,
    )
    desired_canonical = (
        parent_pose
        @ rest_local
        @ wrist_delta_matrix(
            flexion_extension_deg,
            radial_ulnar_deviation_deg,
        )
    )
    desired_rig = rig_basis_from_canonical_pose(
        hand_bone,
        desired_canonical,
    )
    apply_absolute_rig_rotation_via_matrix_basis(
        armature,
        hand_bone["rig_bone"],
        desired_rig,
    )


def _bone_descendants(
    root: bpy.types.Bone,
) -> list[bpy.types.Bone]:
    result = []
    stack = list(root.children)
    while stack:
        bone = stack.pop()
        result.append(bone)
        stack.extend(list(bone.children))
    return result


def _unique_descendant_matching(
    root: bpy.types.Bone,
    predicate,
    label: str,
) -> bpy.types.Bone:
    matches = [
        bone
        for bone in _bone_descendants(root)
        if predicate(bone.name)
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{root.name}: expected one descendant for {label}, "
            f"got {[bone.name for bone in matches]}."
        )
    return matches[0]


def _finger_chain_from_hand_hierarchy(
    armature: bpy.types.Object,
    hand_rig_name: str,
    digit: str,
) -> list[str]:
    hand_bone = armature.data.bones[hand_rig_name]
    token = digit.capitalize()

    # Finger roots are not guaranteed to be direct children of Hand_L/R.
    # The source rig contains intermediate palm/metacarpal nodes, and Ring
    # also carries swapped _L/_R suffixes. Therefore hierarchy membership,
    # not suffix or direct-parent assumptions, is authoritative.
    first = _unique_descendant_matching(
        hand_bone,
        lambda name: name.startswith(f"{token}_1_"),
        f"{digit} segment 1",
    )
    second = _unique_descendant_matching(
        first,
        lambda name: name.startswith(f"{token}_2_"),
        f"{digit} segment 2",
    )
    third = _unique_descendant_matching(
        second,
        lambda name: (
            name.startswith(f"{token}_")
            and not name.startswith(f"{token}_1_")
            and not name.startswith(f"{token}_2_")
        ),
        f"{digit} terminal segment",
    )
    return [first.name, second.name, third.name]


def _pose_bone_length_direction(
    pose_bone: bpy.types.PoseBone,
) -> Vector:
    basis = normalized_basis(pose_bone.matrix)
    return Vector(
        (
            float(basis[0][1]),
            float(basis[1][1]),
            float(basis[2][1]),
        )
    ).normalized()


def _orient_pose_bone_length_to_direction(
    armature: bpy.types.Object,
    rig_name: str,
    target_direction: Vector,
) -> None:
    pose_bone = armature.pose.bones[rig_name]
    current_basis = normalized_basis(pose_bone.matrix)
    current_direction = _pose_bone_length_direction(pose_bone)
    target = Vector(target_direction).normalized()
    swing = current_direction.rotation_difference(target).to_matrix()
    desired_basis = swing @ current_basis
    apply_absolute_rig_rotation_via_matrix_basis(
        armature,
        rig_name,
        desired_basis,
    )


def _ballet_hand_palm_frame(
    armature: bpy.types.Object,
    hand_rig_name: str,
    chains: dict[str, list[str]],
) -> tuple[Vector, Vector, Vector]:
    hand_pose = armature.pose.bones[hand_rig_name]
    index_root = armature.pose.bones[chains["index"][0]]
    middle_root = armature.pose.bones[chains["middle"][0]]
    pinky_root = armature.pose.bones[chains["pinky"][0]]

    longitudinal = (
        Vector(middle_root.head) - Vector(hand_pose.head)
    ).normalized()
    raw_width = Vector(index_root.head) - Vector(pinky_root.head)
    width = raw_width - longitudinal * raw_width.dot(longitudinal)
    if width.length <= 1e-9:
        raise RuntimeError(
            f"{hand_rig_name}: degenerate palm width axis."
        )
    width.normalize()
    normal = longitudinal.cross(width)
    if normal.length <= 1e-9:
        raise RuntimeError(
            f"{hand_rig_name}: degenerate palm normal."
        )
    normal.normalize()
    return longitudinal, width, normal


def apply_ballet_hand_shape(
    armature: bpy.types.Object,
    canonical: dict,
    contract: dict,
) -> dict:
    profile = contract["ballet_hand_shape"]
    digits = list(profile["digits"])
    slopes = profile["lateral_slope_by_digit"]
    normal_keep = float(
        profile["existing_normal_component_preservation"]
    )
    normal_max = float(
        profile["maximum_abs_existing_normal_component"]
    )

    evidence = {
        "status": "PASS",
        "style": profile["style"],
        "finger_bones_only": True,
        "wrist_mutated": False,
        "arm_chain_mutated": False,
        "sides": {},
    }

    for side in ("left", "right"):
        hand_rig_name = canonical["canonical_bones"][
            f"{side}_hand"
        ]["rig_bone"]
        chains = {
            digit: _finger_chain_from_hand_hierarchy(
                armature,
                hand_rig_name,
                digit,
            )
            for digit in digits
        }
        longitudinal, width, normal = _ballet_hand_palm_frame(
            armature,
            hand_rig_name,
            chains,
        )

        for digit in digits:
            digit_slopes = [float(v) for v in slopes[digit]]
            if len(digit_slopes) != len(chains[digit]):
                raise RuntimeError(
                    f"{side}/{digit}: hand-shape slope count mismatch."
                )

            for rig_name, lateral_slope in zip(
                chains[digit],
                digit_slopes,
            ):
                current = _pose_bone_length_direction(
                    armature.pose.bones[rig_name]
                )
                normal_component = max(
                    -normal_max,
                    min(normal_max, float(current.dot(normal))),
                ) * normal_keep
                target = (
                    longitudinal
                    + width * lateral_slope
                    + normal * normal_component
                ).normalized()
                _orient_pose_bone_length_to_direction(
                    armature,
                    rig_name,
                    target,
                )

        evidence["sides"][side] = {
            "hand_rig_bone": hand_rig_name,
            "digit_chains": chains,
            "hierarchy_over_name_suffix": True,
        }

    bpy.context.view_layer.update()
    return evidence


def hand_mesh_inner_edge(
    armature: bpy.types.Object,
    canonical: dict,
    samples: list[tuple[str, int]],
    side: str,
    inner_edge_quantile: float,
) -> dict:
    frame = canonical["body_frame"]["declared_axes_armature_local"]
    left_axis = Vector(frame["left"]).normalized()
    coordinates = [
        float(point.dot(left_axis))
        for point in evaluated_sample_points(armature, samples)
    ]
    q = float(inner_edge_quantile)
    if side == "left":
        inner_edge = quantile(coordinates, q)
        side_offset = inner_edge
    elif side == "right":
        inner_edge = quantile(coordinates, 1.0 - q)
        side_offset = -inner_edge
    else:
        raise RuntimeError(f"Unknown hand side: {side}.")

    return {
        "inner_edge": float(inner_edge),
        "side_offset": float(side_offset),
        "sample_count": len(coordinates),
    }


def solve_hand_mesh_wrist_side(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    pose_entry: dict,
    side: str,
    samples: list[tuple[str, int]],
    inner_edge_quantile: float,
    solver_contract: dict,
) -> dict:
    spacing = pose_entry.get(
        "non_rotational_pose_contract",
        {},
    ).get("hand_mesh_spacing_contract")
    if spacing is None:
        return {"required": False, "status": "NOT_REQUIRED"}

    limits = constraints["joint_limits"]["wrist_2dof"]["dofs"]
    flexion = limits["flexion_extension"]["preferred"]
    deviation = limits["radial_ulnar_deviation"]["preferred"]
    fmin = float(flexion["min"])
    fmax = float(flexion["max"])
    dmin = float(deviation["min"])
    dmax = float(deviation["max"])

    hand_name = f"{side}_hand"
    semantic = pose_entry["evidence"]["hand_wrist_solution"][hand_name]
    semantic_flexion = float(semantic["flexion_extension_deg"])
    semantic_deviation_seed = float(
        semantic["radial_ulnar_deviation_deg"]
    )

    minimum_side_offset = float(spacing["minimum_gap"]) * 0.5
    maximum_side_offset = float(spacing["maximum_gap"]) * 0.5
    epsilon = float(solver_contract["interval_error_epsilon"])
    best = None

    def evaluate(
        flexion_extension_deg: float,
        radial_ulnar_deviation_deg: float,
    ) -> None:
        nonlocal best
        if not fmin <= flexion_extension_deg <= fmax:
            return
        if not dmin <= radial_ulnar_deviation_deg <= dmax:
            return

        apply_hand_wrist_candidate(
            armature,
            canonical,
            side,
            flexion_extension_deg,
            radial_ulnar_deviation_deg,
        )
        measurement = hand_mesh_inner_edge(
            armature,
            canonical,
            samples,
            side,
            inner_edge_quantile,
        )
        side_offset = float(measurement["side_offset"])
        if side_offset < minimum_side_offset:
            interval_error = minimum_side_offset - side_offset
        elif side_offset > maximum_side_offset:
            interval_error = side_offset - maximum_side_offset
        else:
            interval_error = 0.0

        semantic_deviation = (
            abs(flexion_extension_deg - semantic_flexion)
            + abs(radial_ulnar_deviation_deg - semantic_deviation_seed)
        )
        key = (
            interval_error,
            abs(side_offset - minimum_side_offset),
            semantic_deviation,
            abs(flexion_extension_deg),
            abs(radial_ulnar_deviation_deg),
        )
        candidate = {
            "key": key,
            "flexion_extension_deg": float(flexion_extension_deg),
            "radial_ulnar_deviation_deg": float(
                radial_ulnar_deviation_deg
            ),
            "measurement": measurement,
            "interval_error": float(interval_error),
            "semantic_deviation_deg": float(semantic_deviation),
        }
        if best is None or key < best["key"]:
            best = candidate

    coarse = float(solver_contract["coarse_step_deg"])
    f = fmin
    while f <= fmax + 1e-9:
        d = dmin
        while d <= dmax + 1e-9:
            evaluate(f, d)
            d += coarse
        f += coarse

    if best is None:
        raise RuntimeError(
            f"{side}: no preferred wrist candidate exists for hand mesh."
        )

    for step_value in solver_contract["refine_steps_deg"]:
        step = float(step_value)
        center_f = float(best["flexion_extension_deg"])
        center_d = float(best["radial_ulnar_deviation_deg"])
        for f_offset in range(-5, 6):
            for d_offset in range(-5, 6):
                evaluate(
                    center_f + f_offset * step,
                    center_d + d_offset * step,
                )

    apply_hand_wrist_candidate(
        armature,
        canonical,
        side,
        float(best["flexion_extension_deg"]),
        float(best["radial_ulnar_deviation_deg"]),
    )
    final_measurement = hand_mesh_inner_edge(
        armature,
        canonical,
        samples,
        side,
        inner_edge_quantile,
    )

    interval_error = float(best["interval_error"])
    status = "PASS" if interval_error <= epsilon else "FAIL"
    return {
        "required": True,
        "status": status,
        "side": side,
        "solved_flexion_extension_deg": round(
            float(best["flexion_extension_deg"]),
            8,
        ),
        "solved_radial_ulnar_deviation_deg": round(
            float(best["radial_ulnar_deviation_deg"]),
            8,
        ),
        "semantic_seed_flexion_extension_deg": round(
            semantic_flexion,
            8,
        ),
        "semantic_seed_radial_ulnar_deviation_deg": round(
            semantic_deviation_seed,
            8,
        ),
        "inner_edge": round(
            float(final_measurement["inner_edge"]),
            8,
        ),
        "side_offset": round(
            float(final_measurement["side_offset"]),
            8,
        ),
        "minimum_side_offset": round(minimum_side_offset, 8),
        "maximum_side_offset": round(maximum_side_offset, 8),
        "interval_error": round(interval_error, 8),
        "preferred_envelope": {
            "flexion_extension": {"min": fmin, "max": fmax},
            "radial_ulnar_deviation": {"min": dmin, "max": dmax},
        },
        "independent_axial_roll": "BLOCKED",
        "authority": "DEFORMED_HAND_MESH",
    }


def solve_hand_mesh_wrist_spacing(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    pose_entry: dict,
    hand_samples: dict,
    inner_edge_quantile: float,
    solver_contract: dict,
) -> dict:
    side_solutions = {}
    for side in ("left", "right"):
        side_solutions[side] = solve_hand_mesh_wrist_side(
            armature,
            canonical,
            constraints,
            pose_entry,
            side,
            hand_samples[side],
            inner_edge_quantile,
            solver_contract,
        )

    final_spacing = realized_hand_mesh_centerline_spacing(
        armature,
        canonical,
        pose_entry,
        hand_samples,
        inner_edge_quantile,
    )
    status = (
        "PASS"
        if (
            final_spacing["status"] == "PASS"
            and all(
                item["status"] == "PASS"
                for item in side_solutions.values()
            )
        )
        else "FAIL"
    )

    return {
        "status": status,
        "side_solutions": side_solutions,
        "final_mesh_spacing": final_spacing,
        "preferred_only": True,
        "independent_axial_roll": "BLOCKED",
    }


def realized_hand_mesh_centerline_spacing(
    armature: bpy.types.Object,
    canonical: dict,
    pose_entry: dict,
    hand_samples: dict,
    inner_edge_quantile: float,
) -> dict:
    non_rot = pose_entry.get("non_rotational_pose_contract", {})
    contract = non_rot.get("hand_mesh_spacing_contract")
    if contract is None:
        return {"required": False, "status": "NOT_REQUIRED"}

    frame = canonical["body_frame"]["declared_axes_armature_local"]
    left_axis = Vector(frame["left"]).normalized()
    left_points = evaluated_sample_points(
        armature,
        hand_samples["left"],
    )
    right_points = evaluated_sample_points(
        armature,
        hand_samples["right"],
    )
    left_coordinates = [
        float(point.dot(left_axis))
        for point in left_points
    ]
    right_coordinates = [
        float(point.dot(left_axis))
        for point in right_points
    ]

    q = float(inner_edge_quantile)
    left_inner = quantile(left_coordinates, q)
    right_inner = quantile(right_coordinates, 1.0 - q)
    gap = left_inner - right_inner
    minimum = float(contract["minimum_gap"])
    maximum = float(contract["maximum_gap"])
    passed = minimum - 1e-9 <= gap <= maximum + 1e-9

    return {
        "required": True,
        "status": "PASS" if passed else "FAIL",
        "left_inner_edge": round(left_inner, 8),
        "right_inner_edge": round(right_inner, 8),
        "mesh_centerline_gap": round(gap, 8),
        "mesh_centerline_overlap": round(max(0.0, -gap), 8),
        "minimum_allowed_gap": round(minimum, 8),
        "maximum_allowed_gap": round(maximum, 8),
        "inner_edge_quantile": q,
        "left_sample_count": len(left_points),
        "right_sample_count": len(right_points),
        "authority": "DEFORMED_HAND_MESH",
    }


def load_ballet_motion_runtime_modules(repo: Path):
    tools_dir = repo / "tools" / "ballet_motion"
    if str(tools_dir) not in sys.path:
        sys.path.insert(0, str(tools_dir))

    import canonical_pose_solver as pose_solver
    import calibrated_rig_retarget as retarget_solver

    return pose_solver, retarget_solver


def runtime_clearance_physical_upper_bound(
    canonical: dict,
    pose_solver,
) -> float:
    dimensions = pose_solver._canonical_dimensions(canonical)
    maximum_hand_side_offset = (
        float(dimensions["shoulder_half_width"])
        + float(dimensions["upper_arm"])
        + float(dimensions["forearm"])
        + float(dimensions["hand"])
    )
    scale_length = float(dimensions["hand_middle_chain"])
    if scale_length <= 1e-12:
        raise RuntimeError("Degenerate hand-middle scale length.")
    return maximum_hand_side_offset / scale_length


def shoulder_sweep_axis(
    pose_name: str,
    canonical: dict,
) -> Vector:
    frame = canonical["body_frame"]["declared_axes_armature_local"]
    if pose_name == "bras_bas":
        return Vector(frame["front"]).normalized()
    if pose_name == "en_avant":
        return Vector(frame["up"]).normalized()
    raise RuntimeError(
        f"Shoulder sweep is not defined for {pose_name}."
    )


def shoulder_sweep_limit_deg(
    pose_name: str,
    constraints: dict,
    intent_spec: dict,
) -> float:
    semantic = intent_spec["poses"][pose_name][
        "joint_dofs"
    ]["upper_arm"]
    limits = constraints["joint_limits"]["shoulder_ball"]["dofs"]
    margins = []
    for dof_name, value in semantic.items():
        preferred = limits[dof_name]["preferred"]
        value = float(value)
        margins.append(value - float(preferred["min"]))
        margins.append(float(preferred["max"]) - value)

    limit = min(margins)
    if limit <= 0.0:
        raise RuntimeError(
            f"{pose_name}: no preferred shoulder sweep margin remains."
        )
    return float(limit)


def apply_single_shoulder_sweep(
    armature: bpy.types.Object,
    canonical: dict,
    side: str,
    axis: Vector,
    angle_deg: float,
) -> None:
    canonical_name = f"{side}_upper_arm"
    rig_name = canonical["canonical_bones"][
        canonical_name
    ]["rig_bone"]
    pose_bone = armature.pose.bones[rig_name]
    baseline = normalized_basis(pose_bone.matrix)
    rotation = Matrix.Rotation(
        math.radians(float(angle_deg)),
        3,
        axis,
    )
    desired = rotation @ baseline
    apply_absolute_rig_rotation_via_matrix_basis(
        armature,
        rig_name,
        desired,
    )


def solve_runtime_hand_mesh_pose(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    retarget_axis_contract: dict,
    grammar_profile: dict,
    intent_spec: dict,
    pose_name: str,
    hand_samples: dict,
    inner_edge_quantile: float,
    runtime_solver_contract: dict,
    pose_solver,
    retarget_solver,
) -> dict:
    del retarget_axis_contract, grammar_profile, pose_solver, retarget_solver

    if pose_name not in ("bras_bas", "en_avant"):
        raise RuntimeError(
            f"Shoulder-sweep hand solve not defined for {pose_name}."
        )

    # The caller has already selected the Phase 10.6.6 pose entry and
    # applied it. Capture that exact local chain as immutable authority.
    base_pose = {
        bone.name: bone.matrix_basis.copy()
        for bone in armature.pose.bones
    }
    axis = shoulder_sweep_axis(pose_name, canonical)
    sweep_limit = shoulder_sweep_limit_deg(
        pose_name,
        constraints,
        intent_spec,
    )
    spacing = None

    # Recover the active pose entry contract from the already-applied
    # calibrated pose by reading the hand-gap scale from intent/canonical
    # dimensions. No new canonical/retarget solve occurs here.
    dimensions = body_metrics_for_hand(canonical)
    gap_spec = intent_spec["poses"][pose_name][
        "hand_mesh_gap_chain_fraction"
    ]
    minimum_gap = (
        dimensions["hand_middle_chain"]
        * float(gap_spec["min"])
    )
    maximum_gap = (
        dimensions["hand_middle_chain"]
        * float(gap_spec["max"])
    )
    target_side_offset = (
        minimum_gap + maximum_gap
    ) * 0.25

    root_iterations = int(
        runtime_solver_contract["root_iterations"]
    )

    def restore_base_pose() -> None:
        for bone in armature.pose.bones:
            bone.matrix_basis = base_pose[bone.name].copy()
        bpy.context.view_layer.update()

    def evaluate(side: str, angle_deg: float) -> dict:
        restore_base_pose()
        apply_single_shoulder_sweep(
            armature,
            canonical,
            side,
            axis,
            angle_deg,
        )
        measurement = hand_mesh_inner_edge(
            armature,
            canonical,
            hand_samples[side],
            side,
            inner_edge_quantile,
        )
        return {
            "angle_deg": float(angle_deg),
            "side_offset": float(measurement["side_offset"]),
            "measurement": measurement,
        }

    def solve_side(side: str) -> dict:
        center = evaluate(side, 0.0)
        error0 = center["side_offset"] - target_side_offset
        if abs(error0) <= 1e-6:
            return center

        negative = evaluate(side, -sweep_limit)
        positive = evaluate(side, sweep_limit)
        candidates = []
        for endpoint in (negative, positive):
            endpoint_error = (
                endpoint["side_offset"] - target_side_offset
            )
            if error0 * endpoint_error <= 0.0:
                candidates.append(endpoint)

        if not candidates:
            reachable = sorted(
                (
                    negative["side_offset"],
                    center["side_offset"],
                    positive["side_offset"],
                )
            )
            raise RuntimeError(
                f"{pose_name}/{side}: INFEASIBLE_WITHIN_CONSTRAINTS; "
                "primary shoulder sweep cannot reach the declared hand "
                f"mesh target {target_side_offset}; reachable side-offset "
                f"envelope={reachable}; sweep_limit_deg={sweep_limit}."
            )

        endpoint = min(
            candidates,
            key=lambda item: abs(item["angle_deg"]),
        )
        lower = center
        upper = endpoint
        if lower["angle_deg"] > upper["angle_deg"]:
            lower, upper = upper, lower

        lower_error = lower["side_offset"] - target_side_offset
        upper_error = upper["side_offset"] - target_side_offset

        for _ in range(root_iterations):
            midpoint_angle = (
                lower["angle_deg"] + upper["angle_deg"]
            ) * 0.5
            midpoint = evaluate(side, midpoint_angle)
            midpoint_error = (
                midpoint["side_offset"] - target_side_offset
            )
            if abs(midpoint_error) <= 1e-7:
                lower = midpoint
                upper = midpoint
                break
            if lower_error * midpoint_error <= 0.0:
                upper = midpoint
                upper_error = midpoint_error
            else:
                lower = midpoint
                lower_error = midpoint_error

        result = min(
            (lower, upper),
            key=lambda item: abs(
                item["side_offset"] - target_side_offset
            ),
        )
        if (
            abs(result["side_offset"] - target_side_offset)
            > 0.00002
        ):
            raise RuntimeError(
                f"{pose_name}/{side}: shoulder-sweep root solve did not "
                f"converge; target={target_side_offset}; result={result}."
            )
        return result

    solved = {
        side: solve_side(side)
        for side in ("left", "right")
    }

    restore_base_pose()
    for side in ("left", "right"):
        apply_single_shoulder_sweep(
            armature,
            canonical,
            side,
            axis,
            solved[side]["angle_deg"],
        )

    # The two shoulder rotations are now simultaneously active. Forearm
    # and hand matrix_basis values were never changed, so the rounded
    # elbow and wrist relation from Phase 10.6.6 is preserved exactly.
    left_final = hand_mesh_inner_edge(
        armature,
        canonical,
        hand_samples["left"],
        "left",
        inner_edge_quantile,
    )
    right_final = hand_mesh_inner_edge(
        armature,
        canonical,
        hand_samples["right"],
        "right",
        inner_edge_quantile,
    )
    final_gap = (
        float(left_final["side_offset"])
        + float(right_final["side_offset"])
    )

    if float(left_final["side_offset"]) < 0.0:
        raise RuntimeError(
            f"{pose_name}: left hand crosses centerline."
        )
    if float(right_final["side_offset"]) < 0.0:
        raise RuntimeError(
            f"{pose_name}: right hand crosses centerline."
        )
    if not (
        minimum_gap - 1e-6
        <= final_gap
        <= maximum_gap + 1e-6
    ):
        raise RuntimeError(
            f"{pose_name}: final shoulder-sweep mesh gap "
            f"{final_gap} outside [{minimum_gap}, {maximum_gap}]."
        )

    realized = {
        "required": True,
        "status": "PASS",
        "left_inner_edge": round(
            float(left_final["inner_edge"]),
            8,
        ),
        "right_inner_edge": round(
            float(right_final["inner_edge"]),
            8,
        ),
        "mesh_centerline_gap": round(final_gap, 8),
        "mesh_centerline_overlap": 0.0,
        "minimum_allowed_gap": round(minimum_gap, 8),
        "maximum_allowed_gap": round(maximum_gap, 8),
        "inner_edge_quantile": float(inner_edge_quantile),
        "left_sample_count": int(left_final["sample_count"]),
        "right_sample_count": int(right_final["sample_count"]),
        "authority": "DEFORMED_HAND_MESH",
    }

    return {
        "status": "PASS",
        "pose_entry": None,
        "final_mesh_spacing": realized,
        "wrist_seed_evidence": {
            "status": "PASS",
            "source": "PHASE_10_6_6_LOCAL_CHAIN_PRESERVED",
            "preferred_envelope_pass": True,
            "secondary_wrist_trim_applied": False,
            "independent_axial_roll": "BLOCKED",
        },
        "evidence": {
            "method": runtime_solver_contract["method"],
            "primary_joint": "SHOULDER",
            "elbow_local_bend_preserved": True,
            "wrist_local_bend_preserved": True,
            "shoulder_axis": runtime_solver_contract[
                "shoulder_axis_by_pose"
            ][pose_name],
            "shoulder_sweep_limit_deg": round(
                sweep_limit,
                8,
            ),
            "target_side_offset": round(
                target_side_offset,
                8,
            ),
            "solved_shoulder_sweep_deg": {
                side: round(
                    float(item["angle_deg"]),
                    8,
                )
                for side, item in solved.items()
            },
            "final_mesh_side_offsets": {
                "left": round(
                    float(left_final["side_offset"]),
                    8,
                ),
                "right": round(
                    float(right_final["side_offset"]),
                    8,
                ),
            },
            "final_mesh_spacing": realized,
        },
    }


def body_metrics_for_hand(canonical: dict) -> dict:
    bones = canonical["canonical_bones"]
    hand = (
        float(bones["left_hand"]["length"])
        + float(bones["right_hand"]["length"])
    ) * 0.5
    middle = (
        float(bones["left_middle"]["length"])
        + float(bones["right_middle"]["length"])
    ) * 0.5
    return {
        "hand_middle_chain": hand + middle,
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
    grammar_path = Path(args.grammar_profile).resolve()
    intent_path = Path(args.intent_spec).resolve()
    contract_path = Path(args.contract).resolve()
    output_path = Path(args.output).resolve()

    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    retarget = json.loads(retarget_path.read_text(encoding="utf-8"))
    constraints = json.loads(constraint_path.read_text(encoding="utf-8"))
    retarget_axis_contract = json.loads(
        axis_contract_path.read_text(encoding="utf-8")
    )
    grammar_profile = json.loads(
        grammar_path.read_text(encoding="utf-8")
    )
    intent_spec = json.loads(
        intent_path.read_text(encoding="utf-8")
    )
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    pose_solver, retarget_solver = load_ballet_motion_runtime_modules(
        repo
    )

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

    hand_groups = hand_rig_vertex_groups(
        armature,
        canonical,
    )
    hand_required_groups = set().union(*hand_groups.values())
    hand_meshes = relevant_mesh_objects(
        armature,
        hand_required_groups,
    )
    hand_sampling = contract["hand_mesh_sampling"]
    hand_samples = {
        side: collect_weighted_samples(
            hand_meshes,
            hand_groups[side],
            float(
                hand_sampling[
                    "minimum_vertex_group_weight"
                ]
            ),
        )
        for side in ("left", "right")
    }

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

        hand_shape_evidence = apply_ballet_hand_shape(
            armature,
            canonical,
            contract,
        )

        hand_mesh_runtime_solution = {}
        hand_mesh_wrist_solution = {}
        hand_mesh_spacing = {}
        if pose_name in ("bras_bas", "en_avant"):
            hand_mesh_runtime_solution = solve_runtime_hand_mesh_pose(
                armature,
                canonical,
                constraints,
                retarget_axis_contract,
                grammar_profile,
                intent_spec,
                pose_name,
                hand_samples,
                float(hand_sampling["inner_edge_quantile"]),
                contract["hand_mesh_runtime_clearance_solver"],
                pose_solver,
                retarget_solver,
            )
            hand_mesh_wrist_solution = hand_mesh_runtime_solution[
                "wrist_seed_evidence"
            ]
            hand_mesh_spacing = hand_mesh_runtime_solution[
                "final_mesh_spacing"
            ]

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
                anchors,
                rest_heights,
                float(sampling["low_height_quantile"]),
                float(
                    thresholds[
                        "full_foot_seed_up_alignment_min_dot"
                    ]
                ),
                float(
                    thresholds[
                        "full_foot_mesh_search_coarse_step_deg"
                    ]
                ),
                [
                    float(value)
                    for value in thresholds[
                        "full_foot_mesh_search_refine_steps_deg"
                    ]
                ],
            )

        non_rot = pose_entry.get("non_rotational_pose_contract", {})
        scalars = non_rot.get("translation_contact_scalars", {})

        if pose_name == "releve":
            target_heights = {
                "left": float(scalars["left_heel_height"]),
                "right": float(scalars["right_heel_height"]),
            }
            releve_realization = solve_releve_plantar_toe_for_mesh_heel_height(
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
                float(
                    thresholds[
                        "releve_toe_search_coarse_step_deg"
                    ]
                ),
                [
                    float(value)
                    for value in thresholds[
                        "releve_joint_search_refine_steps_deg"
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
                f"> tolerance {contact_tolerance}; "
                f"errors={proof['errors']}; "
                f"root_shift={shift}; "
                f"full_foot_orientation={contact_orientation}.",
            )

        consistency = {}
        fingertip_spacing = {}
        if pose_name in ("bras_bas", "en_avant"):
            fingertip_spacing = realized_middle_fingertip_spacing(
                armature,
                canonical,
                pose_entry,
            )
            consistency["fingertip_spacing_diagnostic"] = (
                fingertip_spacing
            )
            consistency["hand_mesh_spacing"] = hand_mesh_spacing
            consistency["hand_mesh_wrist_solution"] = (
                hand_mesh_wrist_solution
            )
            consistency["hand_mesh_runtime_clearance"] = (
                hand_mesh_runtime_solution["evidence"]
            )

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
                f"plie: pelvis descent error {absolute_error} > {allowed}; "
                f"target={target_descent}; actual={actual_descent}; "
                f"root_shift={shift}.",
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
            selected_toe = float(
                releve_realization["toe_flexion_extension_deg"]
            )
            plantar_preferred = preferred["plantar_dorsiflexion"]
            toe_preferred = preferred["toe_flexion_extension"]
            require(
                float(plantar_preferred["min"])
                <= selected_plantar
                <= float(plantar_preferred["max"]),
                "releve: plantar solver left preferred envelope.",
            )
            require(
                float(toe_preferred["min"])
                <= selected_toe
                <= float(toe_preferred["max"]),
                "releve: toe solver left preferred envelope.",
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
                    f"{abs(actual - target)} > {allowed}; "
                    f"target={target}; actual={actual}; "
                    f"selected_plantar={selected_plantar}; "
                    f"selected_toe={selected_toe}; "
                    f"preferred={preferred}; "
                    f"solver_geometry={releve_realization['geometry']}; "
                    f"solver_heel_errors={releve_realization['heel_errors']}.",
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
            consistency["solved_toe_flexion_extension_deg"] = round(
                selected_toe,
                8,
            )
            consistency["releve_joint_preferred_envelope"] = preferred
            consistency["releve_semantic_joint_targets"] = (
                releve_realization["semantic_targets"]
            )

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
            "middle_fingertip_diagnostic": fingertip_spacing,
            "hand_mesh_spacing_realization": hand_mesh_spacing,
            "hand_mesh_wrist_solution": hand_mesh_wrist_solution,
            "hand_mesh_runtime_clearance_solution": (
                hand_mesh_runtime_solution.get("evidence", {})
            ),
            "ballet_hand_shape": hand_shape_evidence,
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
        "hand_mesh_sampling": {
            "bone_scope": contract["hand_mesh_sampling"]["bone_scope"],
            "vertex_group_names": {
                side: sorted(groups)
                for side, groups in hand_groups.items()
            },
            "sample_counts": {
                side: len(samples)
                for side, samples in hand_samples.items()
            },
            "minimum_vertex_group_weight": float(
                hand_sampling["minimum_vertex_group_weight"]
            ),
            "inner_edge_quantile": float(
                hand_sampling["inner_edge_quantile"]
            ),
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
            "releve_plantar_toe_contact_realization_pass": True,
            "releve_heel_lift_consistency_pass": True,
            "middle_bone_tip_diagnostic_recorded": True,
            "hand_mesh_centerline_spacing_pass": True,
            "hand_mesh_retarget_wrist_seed_preserved_pass": True,
            "hand_mesh_runtime_clearance_solver_pass": True,
            "ballet_hand_shape_applied": True,
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
    print("MIDDLE_BONE_TIP=DIAGNOSTIC_ONLY")
    print("HAND_MESH_CENTERLINE_SPACING=PASS")
    print("HAND_MESH_RETARGET_WRIST_SEED_PRESERVED=PASS")
    print("HAND_MESH_RUNTIME_CLEARANCE_SOLVER=PASS")
    print("BALLET_HAND_SHAPE=PASS")
    print("BLENDER_APPLICATION=PERFORMED")
    print("RENDER=NOT_PERFORMED")
    print("GLB_EXPORT=NOT_PERFORMED")


if __name__ == "__main__":
    main()
