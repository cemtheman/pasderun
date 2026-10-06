"""Validate and bridge the accepted Phase 10.6.1 rest-pose measurements.

This module does not import Blender, author animation, or retarget a motion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from validate import ContractError, validate
from schema_validation import require, shape


SCHEMA = json.loads(Path(__file__).with_name("rig_calibration_v0_1.schema.json").read_text(encoding="utf-8"))
UNRESOLVED = ["joint_limits", "bend_planes", "contact_geometry", "landmark_offsets", "center_of_mass"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def repo_path(repo: Path, name: str) -> Path:
    path = (repo.resolve() / name).resolve()
    require(path.is_relative_to(repo.resolve()), "path", "must stay inside repository")
    require(path.is_file(), "path", f"missing {name}")
    return path


def dot(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b))


def cross(a: list[float], b: list[float]) -> list[float]:
    return [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]]


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def frame_valid(frame: dict) -> None:
    left, up, front = (frame[key] for key in ("left", "up", "front"))
    for axis in (left, up, front):
        require(abs(norm(axis) - 1) < 1e-4, "frame", "non-unit anatomical axis")
    require(max(abs(dot(left, up)), abs(dot(left, front)), abs(dot(up, front))) < 1e-4, "frame", "non-orthogonal axes")
    require(norm([x-y for x, y in zip(cross(left, up), front)]) < 1e-4, "frame", "LEFT x UP must equal FRONT")


def validate_calibration(data: dict, rig: dict, seed: dict, repo: Path) -> dict:
    """Reject stale, inconsistent or partial measurements; return validated data."""
    shape(data, SCHEMA, "calibration", SCHEMA["$defs"])
    validate("rig_profile", rig)
    require(seed.get("schema_version") == 1, "seed", "unsupported seed version")
    require(data["rig_profile_id"] == rig["profile_id"], "rig", "profile ID mismatch")
    require(data["source"]["path"] == rig["source_glb"] == seed["source_glb"], "source", "path mismatch")
    require(data["source"]["armature"] == rig["armature"] == seed["expected_armature_name"], "source", "armature mismatch")
    require(data["seed"]["path"] == rig["calibration_seed"], "seed", "path mismatch")
    require(data["seed"]["sha256"] == sha256_file(repo_path(repo, rig["calibration_seed"])), "seed", "SHA-256 mismatch")
    require(data["source"]["sha256"] == sha256_file(repo_path(repo, rig["source_glb"])), "source", "SHA-256 mismatch")
    frame = data["anatomical_frame"]
    require(frame == rig["anatomical_frame"] == seed["declared_anatomical_frame"], "frame", "declared frame mismatch")
    frame_valid(frame)
    require(data["coordinate_space"] == seed["coordinate_space"], "frame", "coordinate space mismatch")
    require(set(data["unresolved"]) == set(UNRESOLVED), "unresolved", "v0.1 must declare all unfinished measurements")
    bones = data["canonical_bones"]
    mapping = seed["canonical_bones"]
    require(set(bones) == set(mapping), "bones", "canonical inventory mismatch")
    require(len({b["rig_bone"] for b in bones.values()}) == len(bones), "bones", "duplicate target bone")
    rig_names = set(mapping.values())
    require(set(rig["landmark_bones"].values()).issubset(rig_names), "rig", "landmark mapping not in seed")
    for name, bone in bones.items():
        require(bone["rig_bone"] == mapping[name], name, "bone name differs from seed")
        require(bone["parent"] is None or bone["parent"] in rig_names or name == "pelvis", name, "parent not in rig inventory")
        if name != "pelvis":
            require(bone["parent"] in rig_names, name, "non-root bone must have a canonical parent")
        delta = [b-a for a, b in zip(bone["head_local"], bone["tail_local"])]
        require(abs(norm(delta) - bone["length"]) <= max(1e-5, bone["length"]*1e-4), name, "length differs from rest endpoints")
        axes = bone["rest_axes"]
        for axis in axes.values():
            require(abs(norm(axis)-1) < 1e-4, name, "rest axis is not unit")
        require(max(abs(dot(axes[a], axes[b])) for a, b in (("x", "y_length"), ("x", "z"), ("y_length", "z"))) < 1e-4, name, "rest axes not orthogonal")
        require(norm([x-y for x, y in zip(cross(axes["x"], axes["y_length"]), axes["z"])]) < 1e-4, name, "rest axes not right-handed")
        require(norm([x-y for x, y in zip(delta, [v*bone["length"] for v in axes["y_length"]])]) <= max(1e-5, bone["length"]*1e-4), name, "rest length axis disagrees with endpoints")
        matrix = bone["matrix_local"]
        require(all(abs(matrix[i][3]-bone["head_local"][i]) < 1e-4 for i in range(3)), name, "rest matrix origin differs from head")
        require(all(abs(matrix[i][j]-axes[key][i]) < 1e-4 for j, key in enumerate(("x", "y_length", "z")) for i in range(3)), name, "rest matrix basis differs from axes")
        require(all(abs(matrix[3][i]-([0, 0, 0, 1][i])) < 1e-4 for i in range(4)), name, "invalid homogeneous matrix")
    for name in bones:
        visited = set()
        current = name
        while current != "pelvis":
            require(current not in visited, name, "parent cycle")
            visited.add(current)
            parent = bones[current]["parent"]
            require(parent in rig_names, name, "parent chain does not reach pelvis")
            current = next(k for k, v in mapping.items() if v == parent)
    segments = data["semantic_segments"]
    require(set(segments) == set(seed["semantic_segments"]), "segments", "segment inventory mismatch")
    by_rig = {bone["rig_bone"]: bone for bone in bones.values()}
    for name, segment in segments.items():
        start, end = seed["semantic_segments"][name]
        require((segment["start_bone"], segment["end_bone"]) == (start, end), name, "segment endpoints mismatch")
        a, b = by_rig[start]["head_local"], by_rig[end]["head_local"]
        delta = [y-x for x, y in zip(a, b)]
        require(norm(delta) > 1e-6, name, "degenerate semantic segment")
        require(norm([x-y/norm(delta) for x, y in zip(segment["direction_local"], delta)]) < 1e-4, name, "segment direction differs from endpoints")
    return data


def build(repo: Path, rig: dict, seed: dict, source: dict) -> dict:
    """Adapt existing Phase 10.6.1 output; do not estimate missing geometry."""
    require(source.get("phase") == "10.6.1" and source.get("schema_version") == 1, "source", "requires Phase 10.6.1 calibration")
    require(source.get("validation", {}).get("passed") is True, "source", "frame validation did not pass")
    require(source.get("frame_policy") == {
        "body_front_is_declared": True,
        "body_front_is_inferred_from_toes": False,
        "pose_dependent_frame_allowed": False,
    }, "source", "frame policy mismatch")
    require(source.get("profile_id") == seed["profile_id"], "source", "seed profile mismatch")
    result = {
        "schema_version": "0.1.0", "profile_id": f"{rig['profile_id']}_calibration_v0_1",
        "rig_profile_id": rig["profile_id"], "source": source["source"],
        "seed": {"path": rig["calibration_seed"], "sha256": sha256_file(repo_path(repo, rig["calibration_seed"]))},
        "coordinate_space": source["coordinate_space"],
        "anatomical_frame": source["declared_anatomical_frame"],
        "canonical_bones": {name: {key: bone[key] for key in ("rig_bone", "parent", "length", "head_local", "tail_local", "matrix_local", "rest_axes")}
                            for name, bone in source["canonical_bones"].items()},
        "semantic_segments": {name: {key: segment[key] for key in ("start_bone", "end_bone", "direction_local")}
                              for name, segment in source["semantic_segments"].items()},
        "calibration_evidence": {"phase": "10.6.1", "rest_pose": True, "frame_validation_passed": True},
        "unresolved": UNRESOLVED.copy(),
    }
    return validate_calibration(result, rig, seed, repo)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True, type=Path)
    parser.add_argument("--phase10-calibration", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads(repo_path(repo, rig["calibration_seed"]).read_text(encoding="utf-8"))
    source = json.loads(args.phase10_calibration.read_text(encoding="utf-8"))
    result = build(repo, rig, seed, source)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"MOTION_STUDIO_RIG_CALIBRATION=PASS {args.output}")


if __name__ == "__main__":
    main()
