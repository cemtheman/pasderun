"""Pas de Run — Phase 10.6.1 Rig Calibration Profile.

This script deliberately does NOT import the old motion authoring module.
It reads the source GLB in rest pose, validates a declared anatomical frame,
and emits an exact rig profile. BODY_FRONT is never inferred from toes,
animation state, or a rendered pose.
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


PHASE = "10.6.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def vec3(value: Vector) -> list[float]:
    return [round(float(value.x), 8), round(float(value.y), 8), round(float(value.z), 8)]


def matrix4(value: Matrix) -> list[list[float]]:
    return [
        [round(float(value[row][col]), 8) for col in range(4)]
        for row in range(4)
    ]


def unit(values: list[float], label: str) -> Vector:
    vector = Vector(values)
    if vector.length <= 0.000001:
        raise RuntimeError(f"Declared axis {label} is zero.")
    vector.normalize()
    return vector


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_armature(expected_name: str) -> bpy.types.Object:
    armatures = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "ARMATURE"
    ]
    if not armatures:
        raise RuntimeError("No Armature object found after GLB import.")

    for armature in armatures:
        if armature.name == expected_name:
            return armature

    names = sorted(obj.name for obj in armatures)
    raise RuntimeError(
        f"Expected armature {expected_name!r}; found {names}."
    )


def normalized_segment(
    bones: bpy.types.Armature,
    start_name: str,
    end_name: str,
) -> Vector:
    vector = bones[end_name].head_local - bones[start_name].head_local
    if vector.length <= 0.000001:
        raise RuntimeError(
            f"Degenerate semantic segment {start_name}->{end_name}."
        )
    return vector.normalized()


def validate_declared_frame(
    bones: bpy.types.Armature,
    frame: dict[str, Vector],
    thresholds: dict,
) -> dict:
    up = frame["up"]
    left = frame["left"]
    front = frame["front"]

    length_error_max = float(thresholds["axis_length_error_max"])
    dot_max = float(thresholds["orthogonality_abs_dot_max"])

    length_errors = {
        name: abs(axis.length - 1.0)
        for name, axis in frame.items()
    }
    if max(length_errors.values()) > length_error_max:
        raise RuntimeError(
            f"Declared anatomical axes are not unit length: {length_errors}"
        )

    orthogonality = {
        "left_dot_up": left.dot(up),
        "left_dot_front": left.dot(front),
        "up_dot_front": up.dot(front),
    }
    if max(abs(value) for value in orthogonality.values()) > dot_max:
        raise RuntimeError(
            f"Declared anatomical axes are not orthogonal: {orthogonality}"
        )

    cross_error = (left.cross(up) - front).length
    if cross_error > 0.0001:
        raise RuntimeError(
            "Declared frame handedness mismatch: expected LEFT x UP = FRONT."
        )

    shoulder_axis = normalized_segment(
        bones, "Upper_Arm_R", "Upper_Arm_L"
    )
    hip_axis = normalized_segment(
        bones, "Upper_Leg_R", "Upper_Leg_L"
    )
    torso_axis = normalized_segment(bones, "Hips", "Head")
    left_foot = normalized_segment(bones, "Foot_L", "Toes_L")
    right_foot = normalized_segment(bones, "Foot_R", "Toes_R")
    average_toe = left_foot + right_foot
    if average_toe.length <= 0.000001:
        raise RuntimeError("Average toe direction is degenerate.")
    average_toe.normalize()

    evidence = {
        "shoulder_side_alignment": shoulder_axis.dot(left),
        "hip_side_alignment": hip_axis.dot(left),
        "torso_up_alignment": torso_axis.dot(up),
        "average_toe_front_alignment": average_toe.dot(front),
    }

    checks = (
        (
            "shoulder_side_alignment",
            float(thresholds["shoulder_side_alignment_min"]),
        ),
        (
            "hip_side_alignment",
            float(thresholds["hip_side_alignment_min"]),
        ),
        (
            "torso_up_alignment",
            float(thresholds["torso_up_alignment_min"]),
        ),
        (
            "average_toe_front_alignment",
            float(thresholds["average_toe_front_alignment_min"]),
        ),
    )
    for name, minimum in checks:
        if evidence[name] < minimum:
            raise RuntimeError(
                f"Declared frame validation failed: {name}="
                f"{evidence[name]:.6f} < {minimum:.6f}"
            )

    return {
        "axis_length_errors": {
            key: round(value, 8)
            for key, value in length_errors.items()
        },
        "orthogonality": {
            key: round(value, 8)
            for key, value in orthogonality.items()
        },
        "left_cross_up_minus_front_length": round(cross_error, 8),
        "geometry_evidence": {
            key: round(value, 8)
            for key, value in evidence.items()
        },
        "passed": True,
    }


def axis_projection(axis: Vector, frame: dict[str, Vector]) -> dict:
    return {
        "left": round(axis.dot(frame["left"]), 8),
        "up": round(axis.dot(frame["up"]), 8),
        "front": round(axis.dot(frame["front"]), 8),
    }


def bone_profile(
    bone: bpy.types.Bone,
    frame: dict[str, Vector],
) -> dict:
    basis = bone.matrix_local.to_3x3()
    x_axis = basis.col[0].normalized()
    y_axis = basis.col[1].normalized()
    z_axis = basis.col[2].normalized()

    return {
        "parent": bone.parent.name if bone.parent else None,
        "use_connect": bool(bone.use_connect),
        "length": round(float(bone.length), 8),
        "head_local": vec3(bone.head_local),
        "tail_local": vec3(bone.tail_local),
        "matrix_local": matrix4(bone.matrix_local),
        "rest_axes": {
            "x": vec3(x_axis),
            "y_length": vec3(y_axis),
            "z": vec3(z_axis),
        },
        "body_frame_projection": {
            "x": axis_projection(x_axis, frame),
            "y_length": axis_projection(y_axis, frame),
            "z": axis_projection(z_axis, frame),
        },
        "basis_determinant": round(float(basis.determinant()), 8),
    }


def semantic_segment_profile(
    bones: bpy.types.Armature,
    start_name: str,
    end_name: str,
    frame: dict[str, Vector],
) -> dict:
    direction = normalized_segment(bones, start_name, end_name)
    return {
        "start_bone": start_name,
        "end_bone": end_name,
        "direction_local": vec3(direction),
        "body_frame_projection": axis_projection(direction, frame),
    }


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    seed_path = Path(args.seed).resolve()
    output_path = Path(args.output).resolve()

    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    source_glb = repo / seed["source_glb"]
    if not source_glb.exists():
        raise FileNotFoundError(source_glb)

    declared = seed["declared_anatomical_frame"]
    frame = {
        "up": unit(declared["up"], "up"),
        "left": unit(declared["left"], "left"),
        "front": unit(declared["front"], "front"),
    }

    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(source_glb))
    if "FINISHED" not in result:
        raise RuntimeError(f"glTF import did not finish: {result}")

    armature = find_armature(seed["expected_armature_name"])
    if armature.animation_data is not None:
        armature.animation_data_clear()

    bones = armature.data.bones
    canonical = seed["canonical_bones"]
    missing = sorted(
        {
            bone_name
            for bone_name in canonical.values()
            if bone_name not in bones
        }
    )
    if missing:
        raise RuntimeError(f"Calibration bones missing: {missing}")

    validation = validate_declared_frame(
        bones,
        frame,
        seed["validation_thresholds"],
    )

    rig_bones = {
        canonical_name: {
            "rig_bone": rig_name,
            **bone_profile(bones[rig_name], frame),
        }
        for canonical_name, rig_name in canonical.items()
    }

    semantic_segments = {
        name: semantic_segment_profile(
            bones,
            pair[0],
            pair[1],
            frame,
        )
        for name, pair in seed["semantic_segments"].items()
    }

    profile = {
        "phase": PHASE,
        "schema_version": seed["schema_version"],
        "profile_id": seed["profile_id"],
        "source": {
            "path": seed["source_glb"],
            "sha256": sha256_file(source_glb),
            "armature": armature.name,
        },
        "coordinate_space": seed["coordinate_space"],
        "declared_anatomical_frame": {
            name: vec3(axis)
            for name, axis in frame.items()
        },
        "frame_policy": {
            "body_front_is_declared": True,
            "body_front_is_inferred_from_toes": False,
            "pose_dependent_frame_allowed": False,
        },
        "validation": validation,
        "canonical_bones": rig_bones,
        "semantic_segments": semantic_segments,
        "notes": seed.get("notes", []),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(profile, indent=2),
        encoding="utf-8",
    )

    print("PHASE10_6_1_RIG_CALIBRATION=PASS")
    print(f"PROFILE={output_path}")
    print(f"SOURCE_SHA256={profile['source']['sha256']}")
    print(
        "FRAME="
        f"LEFT{profile['declared_anatomical_frame']['left']} "
        f"UP{profile['declared_anatomical_frame']['up']} "
        f"FRONT{profile['declared_anatomical_frame']['front']}"
    )


if __name__ == "__main__":
    main()
