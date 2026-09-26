"""One-time repair for swapped Ring_L / Ring_R source bone names.

The source rig geometry and parentage are already correct; only ring-finger
L/R labels are inverted. This migration renames the six ring-chain bones and
matching mesh vertex groups without changing transforms or hierarchy, exports
a new GLB, and writes a validation report. It never overwrites the source GLB.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy


EXPECTED_SOURCE_SHA256 = "a162d8730238a76ba1d6b31910c98fb1f5640c46917983e0bbad04095e81b7b2"

FINAL_RENAMES = {
    # Geometric left hand (+X), currently mislabelled R.
    "Ring_R": "Ring_L",
    "Ring_1_R": "Ring_1_L",
    "Ring_2_R": "Ring_2_L",
    # Geometric right hand (-X), currently mislabelled L.
    "Ring_L": "Ring_R",
    "Ring_1_L": "Ring_1_R",
    "Ring_2_L": "Ring_2_R",
}

EXPECTED_PARENT_AFTER = {
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


def xyz(v):
    return [round(float(x), 8) for x in v]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

    repo = args.repo.resolve()
    source = args.source.resolve()
    output = args.output.resolve()
    report_path = args.report.resolve()

    require(source.is_file(), f"Missing source GLB: {source}")
    require(source != output, "Refusing to overwrite source GLB during migration")

    source_sha = sha256(source)
    require(
        source_sha == EXPECTED_SOURCE_SHA256,
        f"Unexpected source SHA256: {source_sha}",
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))

    rig = bpy.data.objects.get("Rig")
    require(rig is not None and rig.type == "ARMATURE", "Expected armature Rig")

    before = {}
    for name in FINAL_RENAMES:
        bone = rig.data.bones.get(name)
        require(bone is not None, f"Missing source bone {name}")
        before[name] = {
            "parent": bone.parent.name if bone.parent else None,
            "head_local": xyz(bone.head_local),
            "tail_local": xyz(bone.tail_local),
            "length": round(float(bone.length), 8),
        }

    # Validate the exact anomaly before mutating.
    require(before["Ring_R"]["parent"] == "Hand_L", "Ring_R is not under Hand_L as expected")
    require(before["Ring_L"]["parent"] == "Hand_R", "Ring_L is not under Hand_R as expected")
    require(before["Ring_R"]["head_local"][0] > 0, "Ring_R is not on calibrated left (+X)")
    require(before["Ring_L"]["head_local"][0] < 0, "Ring_L is not on calibrated right (-X)")

    temp_names = {old: f"__MS_RING_SWAP__{i}" for i, old in enumerate(FINAL_RENAMES, start=1)}

    # Record deforming mesh vertex groups that need the same rename.
    affected_meshes = []
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if not any(mod.type == "ARMATURE" and mod.object == rig for mod in obj.modifiers):
            continue
        names = {vg.name for vg in obj.vertex_groups}
        touched = sorted(n for n in FINAL_RENAMES if n in names)
        if touched:
            affected_meshes.append({"object": obj.name, "groups": touched})

    # Two-phase rename avoids Blender name collisions.
    for old, temp in temp_names.items():
        rig.data.bones[old].name = temp
    for old, new in FINAL_RENAMES.items():
        rig.data.bones[temp_names[old]].name = new

    # Keep skin weights bound to the renamed bones.
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if not any(mod.type == "ARMATURE" and mod.object == rig for mod in obj.modifiers):
            continue
        groups = {vg.name: vg for vg in obj.vertex_groups}
        vg_temp = {}
        for old in FINAL_RENAMES:
            vg = groups.get(old)
            if vg is not None:
                tmp = temp_names[old]
                vg.name = tmp
                vg_temp[old] = vg
        for old, vg in vg_temp.items():
            vg.name = FINAL_RENAMES[old]

    bpy.context.view_layer.update()

    after = {}
    for name, expected_parent in EXPECTED_PARENT_AFTER.items():
        bone = rig.data.bones.get(name)
        require(bone is not None, f"Missing repaired bone {name}")
        parent = bone.parent.name if bone.parent else None
        require(parent == expected_parent, f"{name}: parent {parent} != {expected_parent}")
        after[name] = {
            "parent": parent,
            "head_local": xyz(bone.head_local),
            "tail_local": xyz(bone.tail_local),
            "length": round(float(bone.length), 8),
        }

    # Geometry must follow identity, not old labels:
    # old Ring_R chain becomes repaired Ring_L chain, and vice versa.
    geometry_pairs = {
        "Ring_L": "Ring_R",
        "Ring_1_L": "Ring_1_R",
        "Ring_2_L": "Ring_2_R",
        "Ring_R": "Ring_L",
        "Ring_1_R": "Ring_1_L",
        "Ring_2_R": "Ring_2_L",
    }
    for repaired, old in geometry_pairs.items():
        require(after[repaired]["head_local"] == before[old]["head_local"],
                f"{repaired}: head geometry changed")
        require(after[repaired]["tail_local"] == before[old]["tail_local"],
                f"{repaired}: tail geometry changed")
        require(after[repaired]["length"] == before[old]["length"],
                f"{repaired}: length changed")

    output.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # Export the complete imported scene as a new GLB.
    bpy.ops.export_scene.gltf(
        filepath=str(output),
        export_format="GLB",
        export_animations=True,
    )
    require(output.is_file(), f"GLB export missing: {output}")

    # Re-import exported file for independent post-export verification.
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(output))
    exported_rig = bpy.data.objects.get("Rig")
    require(exported_rig is not None and exported_rig.type == "ARMATURE",
            "Exported GLB missing Rig")

    exported = {}
    for name, expected_parent in EXPECTED_PARENT_AFTER.items():
        bone = exported_rig.data.bones.get(name)
        require(bone is not None, f"Exported GLB missing {name}")
        parent = bone.parent.name if bone.parent else None
        require(parent == expected_parent,
                f"Exported {name}: parent {parent} != {expected_parent}")
        exported[name] = {
            "parent": parent,
            "head_local": xyz(bone.head_local),
            "tail_local": xyz(bone.tail_local),
            "length": round(float(bone.length), 8),
        }

    # Confirm left/right spatial identities after round-trip.
    require(exported["Ring_L"]["head_local"][0] > 0, "Exported Ring_L is not on +X left")
    require(exported["Ring_R"]["head_local"][0] < 0, "Exported Ring_R is not on -X right")

    report = {
        "status": "RING_NAME_REPAIR_CANDIDATE_PASS",
        "source_glb": str(source),
        "source_sha256": source_sha,
        "output_glb": str(output),
        "output_sha256": sha256(output),
        "rename_map": FINAL_RENAMES,
        "affected_mesh_vertex_groups": affected_meshes,
        "before": before,
        "after_in_blender": after,
        "after_export_roundtrip": exported,
        "checks": {
            "source_sha_match": True,
            "source_anomaly_confirmed": True,
            "hierarchy_preserved": True,
            "geometry_preserved": True,
            "vertex_groups_renamed_with_bones": True,
            "export_roundtrip_passed": True,
            "left_ring_is_positive_x": True,
            "right_ring_is_negative_x": True,
        },
        "limits": (
            "This candidate repairs bone and matching deform vertex-group names only. "
            "The original source GLB is intentionally untouched. Existing generated "
            "calibration/build artifacts tied to the old source SHA must be regenerated "
            "after the repaired GLB is adopted."
        ),
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("MOTION_STUDIO_RING_NAME_REPAIR=CANDIDATE_PASS")
    print(f"SOURCE_SHA256={source_sha}")
    print(f"OUTPUT_SHA256={report['output_sha256']}")
    print(f"OUTPUT={output}")
    print(f"REPORT={report_path}")
    for name in ("Ring_L", "Ring_1_L", "Ring_2_L", "Ring_R", "Ring_1_R", "Ring_2_R"):
        print(f"{name} | parent={exported[name]['parent']} | head={exported[name]['head_local']}")


if __name__ == "__main__":
    main()
