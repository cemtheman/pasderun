"""Pas de Run — Phase 10.6.2 Canonical Ballet Skeleton.

Pure-Python bridge from the exact Phase 10.6.1 rig calibration profile into
a model-independent canonical ballet skeleton. No Blender/Godot runtime,
render, pose authoring, animation, or IK is performed here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from canonical_math import (
    cross,
    determinant,
    dot,
    mat_mul,
    matrix_from_columns,
    normalize,
    orthogonality_error,
    project_orthogonal,
    rotation_matrix_to_quaternion_wxyz,
    rounded_matrix,
    rounded_vector,
    sub,
    transpose,
)


PHASE = "10.6.2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--calibration", required=True)
    parser.add_argument("--spec", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def resolve_axis(name: str, frame: dict[str, list[float]]) -> list[float]:
    axes = {
        "BODY_LEFT": frame["left"],
        "BODY_RIGHT": [-value for value in frame["left"]],
        "BODY_UP": frame["up"],
        "BODY_DOWN": [-value for value in frame["up"]],
        "BODY_FRONT": frame["front"],
        "BODY_BACK": [-value for value in frame["front"]],
    }
    if name not in axes:
        raise RuntimeError(f"Unknown canonical axis token: {name}")
    return normalize(axes[name])


def canonical_basis(
    length_axis_name: str,
    secondary_axis_name: str,
    frame: dict[str, list[float]],
) -> list[list[float]]:
    y_axis = resolve_axis(length_axis_name, frame)
    secondary = resolve_axis(secondary_axis_name, frame)
    z_axis = normalize(project_orthogonal(secondary, y_axis))
    x_axis = normalize(cross(y_axis, z_axis))
    z_axis = normalize(cross(x_axis, y_axis))
    basis = matrix_from_columns(x_axis, y_axis, z_axis)

    require(
        determinant(basis) > 0.999999,
        f"Canonical basis is not right-handed: {length_axis_name}/"
        f"{secondary_axis_name}",
    )
    return basis


def rig_rest_basis(calibration_bone: dict) -> list[list[float]]:
    axes = calibration_bone["rest_axes"]
    return matrix_from_columns(
        axes["x"],
        axes["y_length"],
        axes["z"],
    )


def body_coordinates(
    point: list[float],
    origin: list[float],
    frame: dict[str, list[float]],
) -> dict[str, float]:
    delta = sub(point, origin)
    return {
        "left": round(dot(delta, frame["left"]), 8),
        "up": round(dot(delta, frame["up"]), 8),
        "front": round(dot(delta, frame["front"]), 8),
    }


def validate_spec_graph(spec: dict) -> None:
    bones = spec["bones"]
    require("pelvis" in bones, "Canonical skeleton must define pelvis.")
    require(bones["pelvis"]["parent"] is None, "Pelvis must be canonical root.")

    for name, bone in bones.items():
        parent = bone["parent"]
        if parent is not None:
            require(parent in bones, f"{name} references missing parent {parent}.")
        require(
            bone["joint_class"] in spec["joint_classes"],
            f"{name} uses unknown joint class {bone['joint_class']}.",
        )

    for start in bones:
        seen = set()
        current = start
        while current is not None:
            require(current not in seen, f"Canonical hierarchy cycle at {start}.")
            seen.add(current)
            current = bones[current]["parent"]


def paired_length_evidence(
    spec: dict,
    calibration_bones: dict,
) -> list[dict]:
    evidence = []
    for left_name, right_name in spec["bilateral_pairs"]:
        left_length = float(calibration_bones[left_name]["length"])
        right_length = float(calibration_bones[right_name]["length"])
        scale = max(left_length, right_length, 1e-12)
        evidence.append(
            {
                "left": left_name,
                "right": right_name,
                "left_length": round(left_length, 8),
                "right_length": round(right_length, 8),
                "relative_difference": round(
                    abs(left_length - right_length) / scale,
                    8,
                ),
            }
        )
    return evidence


def skeleton_metrics(calibration_bones: dict) -> dict:
    def bone_length(name: str) -> float:
        return float(calibration_bones[name]["length"])

    return {
        "left_arm_chain_length": round(
            bone_length("left_upper_arm")
            + bone_length("left_forearm")
            + bone_length("left_hand"),
            8,
        ),
        "right_arm_chain_length": round(
            bone_length("right_upper_arm")
            + bone_length("right_forearm")
            + bone_length("right_hand"),
            8,
        ),
        "left_leg_chain_length": round(
            bone_length("left_thigh")
            + bone_length("left_shin")
            + bone_length("left_foot"),
            8,
        ),
        "right_leg_chain_length": round(
            bone_length("right_thigh")
            + bone_length("right_shin")
            + bone_length("right_foot"),
            8,
        ),
    }


def build_bone_entry(
    name: str,
    spec_bone: dict,
    calibration_bone: dict,
    frame: dict[str, list[float]],
    pelvis_origin: list[float],
    thresholds: dict,
) -> dict:
    canonical = canonical_basis(
        spec_bone["length_axis"],
        spec_bone["secondary_axis"],
        frame,
    )
    rig = rig_rest_basis(calibration_bone)

    canonical_error = orthogonality_error(canonical)
    rig_error = orthogonality_error(rig)
    require(
        canonical_error <= float(
            thresholds["canonical_basis_orthogonality_max_error"]
        ),
        f"{name}: canonical basis orthogonality error {canonical_error}.",
    )
    require(
        rig_error <= float(
            thresholds["bind_rotation_orthogonality_max_error"]
        ),
        f"{name}: rig rest basis orthogonality error {rig_error}.",
    )

    canonical_to_rig = mat_mul(rig, transpose(canonical))
    rig_to_canonical = transpose(canonical_to_rig)
    bind_error = orthogonality_error(canonical_to_rig)
    bind_det = determinant(canonical_to_rig)

    require(
        bind_error <= float(thresholds["bind_rotation_orthogonality_max_error"]),
        f"{name}: bind rotation orthogonality error {bind_error}.",
    )
    require(
        float(thresholds["bind_rotation_determinant_min"])
        <= bind_det
        <= float(thresholds["bind_rotation_determinant_max"]),
        f"{name}: bind rotation determinant {bind_det}.",
    )

    return {
        "parent": spec_bone["parent"],
        "side": spec_bone["side"],
        "joint_class": spec_bone["joint_class"],
        "joint_dofs": spec_bone.get("joint_dofs"),
        "rig_bone": calibration_bone["rig_bone"],
        "length": calibration_bone["length"],
        "head_body": body_coordinates(
            calibration_bone["head_local"],
            pelvis_origin,
            frame,
        ),
        "tail_body": body_coordinates(
            calibration_bone["tail_local"],
            pelvis_origin,
            frame,
        ),
        "canonical_rest_contract": {
            "length_axis": spec_bone["length_axis"],
            "secondary_axis": spec_bone["secondary_axis"],
            "basis_armature_local": rounded_matrix(canonical),
        },
        "rig_rest_basis_armature_local": rounded_matrix(rig),
        "retarget_bind": {
            "canonical_to_rig_rotation_matrix": rounded_matrix(
                canonical_to_rig
            ),
            "canonical_to_rig_quaternion_wxyz": rounded_vector(
                rotation_matrix_to_quaternion_wxyz(canonical_to_rig)
            ),
            "rig_to_canonical_rotation_matrix": rounded_matrix(
                rig_to_canonical
            ),
            "orthogonality_error": round(bind_error, 10),
            "determinant": round(bind_det, 10),
        },
        "evidence": {
            "canonical_basis_orthogonality_error": round(
                canonical_error, 10
            ),
            "rig_basis_orthogonality_error": round(rig_error, 10),
        },
    }


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    calibration_path = Path(args.calibration).resolve()
    spec_path = Path(args.spec).resolve()
    output_path = Path(args.output).resolve()

    calibration = json.loads(calibration_path.read_text(encoding="utf-8"))
    spec = json.loads(spec_path.read_text(encoding="utf-8"))

    require(calibration["phase"] == "10.6.1", "Requires Phase 10.6.1 profile.")
    require(calibration["validation"]["passed"], "Rig calibration did not pass.")
    policy = calibration["frame_policy"]
    require(policy["body_front_is_declared"], "BODY_FRONT is not declared.")
    require(
        not policy["body_front_is_inferred_from_toes"],
        "BODY_FRONT was inferred from toes.",
    )
    require(
        not policy["pose_dependent_frame_allowed"],
        "Pose-dependent body frame is forbidden.",
    )

    validate_spec_graph(spec)

    source_path = repo / calibration["source"]["path"]
    require(source_path.exists(), f"Source GLB missing: {source_path}")
    actual_sha = sha256_file(source_path)
    require(
        actual_sha == calibration["source"]["sha256"],
        "Calibration profile is stale: source GLB SHA-256 changed.",
    )

    frame = calibration["declared_anatomical_frame"]
    calibration_bones = calibration["canonical_bones"]
    missing = sorted(set(spec["bones"]) - set(calibration_bones))
    require(not missing, f"Calibration missing canonical bones: {missing}")

    pelvis_origin = calibration_bones["pelvis"]["head_local"]
    thresholds = spec["validator_foundation"]

    canonical_bones = {
        name: build_bone_entry(
            name,
            bone_spec,
            calibration_bones[name],
            frame,
            pelvis_origin,
            thresholds,
        )
        for name, bone_spec in spec["bones"].items()
    }

    output = {
        "phase": PHASE,
        "schema_version": 1,
        "profile_id": (
            f"{calibration['profile_id']}__{spec['spec_id']}"
        ),
        "source": calibration["source"],
        "calibration_phase": calibration["phase"],
        "canonical_spec": {
            "id": spec["spec_id"],
            "schema_version": spec["schema_version"],
        },
        "body_frame": {
            "components": ["LEFT", "UP", "FRONT"],
            "declared_axes_armature_local": frame,
            "origin": "pelvis.head_local",
            "front_policy": "DECLARED_BY_RIG_CALIBRATION_ONLY",
        },
        "solver_policy": spec["solver_policy"],
        "joint_classes": spec["joint_classes"],
        "canonical_bones": canonical_bones,
        "metrics": skeleton_metrics(calibration_bones),
        "bilateral_length_evidence": paired_length_evidence(
            spec,
            calibration_bones,
        ),
        "validator_foundation": {
            "source_sha_match": True,
            "canonical_graph_valid": True,
            "all_bind_rotations_right_handed": True,
            "pose_validators_reserved": thresholds[
                "pose_validators_reserved"
            ],
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(output, indent=2),
        encoding="utf-8",
    )

    print("PHASE10_6_2_CANONICAL_SKELETON=PASS")
    print(f"PROFILE={output_path}")
    print(f"BONES={len(canonical_bones)}")
    print("BODY_FRAME=LEFT,UP,FRONT")
    print("FRONT_POLICY=DECLARED_BY_RIG_CALIBRATION_ONLY")


if __name__ == "__main__":
    main()
