"""Repair the ring-finger deform vertex-group side swap in the canonical source.

Context
-------
The v0.1 ring-name migration renamed bones and then manually renamed matching
vertex groups. Blender already propagates bone renames to matching deform
groups for meshes bound to the armature. The second manual pass therefore
swapped the ring vertex groups a second time: bone names/hierarchy became
correct, while Ring_L weights ended up on the geometric right side and Ring_R
weights on the geometric left side. Posing either ring chain then stretches
remote vertices into long spikes.

This migration starts from the currently repaired canonical GLB (SHA pinned
below), leaves all bones/transforms/hierarchy untouched, swaps ONLY the six
ring-chain vertex-group names, exports a separate candidate GLB, re-imports it,
and validates weighted-vertex centroids against the calibrated left/right side.

It never overwrites the canonical source directly.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy


EXPECTED_SOURCE_SHA256 = "ae03b92e46f71db3630872f9ba212e6700561164c71ca1f6576c58996ce7bea8"

SWAP = {
    "Ring_L": "Ring_R",
    "Ring_1_L": "Ring_1_R",
    "Ring_2_L": "Ring_2_R",
    "Ring_R": "Ring_L",
    "Ring_1_R": "Ring_1_L",
    "Ring_2_R": "Ring_2_L",
}

EXPECTED_PARENT = {
    "Ring_L": "Hand_L",
    "Ring_1_L": "Ring_L",
    "Ring_2_L": "Ring_1_L",
    "Ring_R": "Hand_R",
    "Ring_1_R": "Ring_R",
    "Ring_2_R": "Ring_1_R",
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def group_weighted_centroid_x(obj, group_name: str, rig) -> dict:
    vg = obj.vertex_groups.get(group_name)
    if vg is None:
        return {"present": False, "weighted_vertices": 0, "weight_sum": 0.0, "centroid_x": None}

    group_index = vg.index
    to_rig = rig.matrix_world.inverted() @ obj.matrix_world
    weighted = 0
    weight_sum = 0.0
    x_sum = 0.0
    for vertex in obj.data.vertices:
        for assignment in vertex.groups:
            if assignment.group == group_index and assignment.weight > 0.0:
                point = to_rig @ vertex.co
                weighted += 1
                weight_sum += assignment.weight
                x_sum += point.x * assignment.weight
                break

    return {
        "present": True,
        "weighted_vertices": weighted,
        "weight_sum": round(weight_sum, 8),
        "centroid_x": round(x_sum / weight_sum, 8) if weight_sum > 0.0 else None,
    }


def audit_groups(rig):
    audit = {}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if not any(mod.type == "ARMATURE" and mod.object == rig for mod in obj.modifiers):
            continue
        groups = {}
        for name in SWAP:
            info = group_weighted_centroid_x(obj, name, rig)
            if info["present"]:
                groups[name] = info
        if groups:
            audit[obj.name] = groups
    return audit


def aggregate_centroid_x(audit, names):
    total_weight = 0.0
    weighted_x = 0.0
    vertices = 0
    for groups in audit.values():
        for name in names:
            info = groups.get(name)
            if not info or info["centroid_x"] is None or info["weight_sum"] <= 0:
                continue
            total_weight += info["weight_sum"]
            weighted_x += info["centroid_x"] * info["weight_sum"]
            vertices += info["weighted_vertices"]
    return {
        "weighted_vertices": vertices,
        "weight_sum": round(total_weight, 8),
        "centroid_x": round(weighted_x / total_weight, 8) if total_weight > 0 else None,
    }


def side_summary(audit):
    return {
        "L": aggregate_centroid_x(audit, ("Ring_L", "Ring_1_L", "Ring_2_L")),
        "R": aggregate_centroid_x(audit, ("Ring_R", "Ring_1_R", "Ring_2_R")),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

    source = args.source.resolve()
    output = args.output.resolve()
    report_path = args.report.resolve()

    require(source.is_file(), f"Missing source GLB: {source}")
    require(source != output, "Refusing to overwrite canonical source")
    source_sha = sha256(source)
    require(source_sha == EXPECTED_SOURCE_SHA256, f"Unexpected source SHA256: {source_sha}")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    rig = bpy.data.objects.get("Rig")
    require(rig is not None and rig.type == "ARMATURE", "Expected armature Rig")

    # Bone repair from v0.1 must remain intact.
    for name, parent_expected in EXPECTED_PARENT.items():
        bone = rig.data.bones.get(name)
        require(bone is not None, f"Missing bone {name}")
        parent = bone.parent.name if bone.parent else None
        require(parent == parent_expected, f"{name}: parent {parent} != {parent_expected}")
    require(rig.data.bones["Ring_L"].head_local.x > 0, "Ring_L bone is not geometric left (+X)")
    require(rig.data.bones["Ring_R"].head_local.x < 0, "Ring_R bone is not geometric right (-X)")

    before = audit_groups(rig)
    before_side = side_summary(before)
    require(before_side["L"]["centroid_x"] is not None, "No Ring_L deform weights found")
    require(before_side["R"]["centroid_x"] is not None, "No Ring_R deform weights found")

    # The corruption signature we expect: L-labelled weights live on -X and
    # R-labelled weights live on +X despite correctly repaired bone locations.
    require(before_side["L"]["centroid_x"] < 0,
            f"Expected Ring_L weights on wrong (-X) side, got {before_side['L']['centroid_x']}")
    require(before_side["R"]["centroid_x"] > 0,
            f"Expected Ring_R weights on wrong (+X) side, got {before_side['R']['centroid_x']}")

    temp = {old: f"__MS_RING_VG_SWAP__{i}" for i, old in enumerate(SWAP, start=1)}
    touched = {}

    # IMPORTANT: swap vertex groups only. Bones are already correct and must not
    # be renamed in this migration.
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if not any(mod.type == "ARMATURE" and mod.object == rig for mod in obj.modifiers):
            continue

        original_groups = {name: obj.vertex_groups.get(name) for name in SWAP}
        existing = {name: vg for name, vg in original_groups.items() if vg is not None}
        if not existing:
            continue

        for old, vg in existing.items():
            vg.name = temp[old]
        for old, vg in existing.items():
            vg.name = SWAP[old]

        touched[obj.name] = sorted(existing)

    bpy.context.view_layer.update()

    after = audit_groups(rig)
    after_side = side_summary(after)
    require(after_side["L"]["centroid_x"] is not None and after_side["L"]["centroid_x"] > 0,
            f"Ring_L weights not repaired to +X: {after_side['L']['centroid_x']}")
    require(after_side["R"]["centroid_x"] is not None and after_side["R"]["centroid_x"] < 0,
            f"Ring_R weights not repaired to -X: {after_side['R']['centroid_x']}")

    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(filepath=str(output), export_format="GLB", export_animations=True)
    require(output.is_file(), "Candidate GLB was not exported")

    # Round-trip verification.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(output))
    exported_rig = bpy.data.objects.get("Rig")
    require(exported_rig is not None and exported_rig.type == "ARMATURE", "Round-trip Rig missing")

    for name, parent_expected in EXPECTED_PARENT.items():
        bone = exported_rig.data.bones.get(name)
        require(bone is not None, f"Round-trip missing bone {name}")
        parent = bone.parent.name if bone.parent else None
        require(parent == parent_expected, f"Round-trip {name}: parent {parent} != {parent_expected}")

    roundtrip = audit_groups(exported_rig)
    roundtrip_side = side_summary(roundtrip)
    require(roundtrip_side["L"]["centroid_x"] is not None and roundtrip_side["L"]["centroid_x"] > 0,
            "Round-trip Ring_L weights are not +X")
    require(roundtrip_side["R"]["centroid_x"] is not None and roundtrip_side["R"]["centroid_x"] < 0,
            "Round-trip Ring_R weights are not -X")

    report = {
        "status": "RING_VERTEX_GROUP_REPAIR_CANDIDATE_PASS",
        "source_sha256": source_sha,
        "output_sha256": sha256(output),
        "touched_meshes": touched,
        "before": before,
        "before_side_summary": before_side,
        "after_in_blender": after,
        "after_side_summary": after_side,
        "roundtrip": roundtrip,
        "roundtrip_side_summary": roundtrip_side,
        "checks": {
            "source_sha_match": True,
            "bone_names_and_hierarchy_unchanged": True,
            "corruption_signature_confirmed": True,
            "vertex_groups_only_swapped": True,
            "left_weights_positive_x": True,
            "right_weights_negative_x": True,
            "export_roundtrip_passed": True,
        },
        "limits": (
            "This candidate repairs only the ring deform vertex-group side swap introduced "
            "by the earlier migration. It does not alter bone transforms, hierarchy, other "
            "weights, or animation data. Canonical source replacement remains a separate step."
        ),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("MOTION_STUDIO_RING_VERTEX_GROUP_REPAIR=CANDIDATE_PASS")
    print(f"SOURCE_SHA256={source_sha}")
    print(f"OUTPUT_SHA256={report['output_sha256']}")
    print(f"BEFORE_L_X={before_side['L']['centroid_x']}")
    print(f"BEFORE_R_X={before_side['R']['centroid_x']}")
    print(f"AFTER_L_X={after_side['L']['centroid_x']}")
    print(f"AFTER_R_X={after_side['R']['centroid_x']}")
    print(f"OUTPUT={output}")
    print(f"REPORT={report_path}")


if __name__ == "__main__":
    main()
