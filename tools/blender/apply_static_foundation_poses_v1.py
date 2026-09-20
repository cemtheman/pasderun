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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--canonical-profile", required=True)
    parser.add_argument("--retarget-profile", required=True)
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
    contract_path = Path(args.contract).resolve()
    output_path = Path(args.output).resolve()

    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    retarget = json.loads(retarget_path.read_text(encoding="utf-8"))
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    require(canonical["phase"] == "10.6.2", "Requires Phase 10.6.2 canonical profile.")
    require(retarget["phase"] == "10.6.6", "Requires Phase 10.6.6 retarget profile.")
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
        non_rot = pose_entry.get("non_rotational_pose_contract", {})
        scalars = non_rot.get("translation_contact_scalars", {})

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

        pose_reports[pose_name] = {
            "root_translation_mode": mode,
            "root_translation_armature_local": [
                round(float(value), 8)
                for value in desired_translation
            ],
            "root_up_shift": round(float(shift), 8),
            "rotation_application": rotation_errors,
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
            "full_foot_contact_pass": True,
            "forefoot_contact_pass": True,
            "plie_root_descent_consistency_pass": True,
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
    print("FULL_FOOT_CONTACT=PASS")
    print("FOREFOOT_CONTACT=PASS")
    print("PLIE_ROOT_DESCENT=PASS")
    print("RELEVE_HEEL_LIFT=PASS")
    print("BLENDER_APPLICATION=PERFORMED")
    print("RENDER=NOT_PERFORMED")
    print("GLB_EXPORT=NOT_PERFORMED")


if __name__ == "__main__":
    main()
