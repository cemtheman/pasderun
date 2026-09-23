#!/usr/bin/env python3
"""Phase 11.3 — final-rig stumble/recovery authoring lab.

The authored source .blend is loaded only as a visual/temporal reference.
No source bone drives, constrains, retargets, or copies rotation to the target.
The only animation authority created here is stumble_recovery_v1 on the actual
low_poly_girl Rig. Key poses are authored in later bounded passes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PHASE = "11.3"
ACTION_NAME = "stumble_recovery_v1"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source-blend", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(argv)


def find_armature(name: str) -> bpy.types.Object:
    armature = bpy.data.objects.get(name)
    require(
        armature is not None and armature.type == "ARMATURE",
        f"Expected armature {name!r} not found.",
    )
    return armature


def scene_bounds(objects: list[bpy.types.Object]) -> tuple[Vector, Vector]:
    points: list[Vector] = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        for corner in obj.bound_box:
            points.append(obj.matrix_world @ Vector(corner))
    require(points, "No mesh bounds available for authoring layout.")
    minimum = Vector((
        min(p.x for p in points),
        min(p.y for p in points),
        min(p.z for p in points),
    ))
    maximum = Vector((
        max(p.x for p in points),
        max(p.y for p in points),
        max(p.z for p in points),
    ))
    return minimum, maximum


def clear_target_pose(armature: bpy.types.Object) -> None:
    for pb in armature.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)
    bpy.context.view_layer.update()


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    source_blend = Path(args.source_blend).resolve()
    contract_path = Path(args.contract).resolve()
    output_blend = Path(args.output_blend).resolve()
    report_path = Path(args.report).resolve()

    require(source_blend.exists(), f"Source blend missing: {source_blend}")
    require(contract_path.exists(), f"Contract missing: {contract_path}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    bpy.ops.wm.open_mainfile(filepath=str(source_blend))
    scene = bpy.context.scene

    source_cfg = contract["source_reference"]
    source_armature = find_armature(source_cfg["expected_armature"])
    source_action = bpy.data.actions.get(source_cfg["expected_action"])
    require(
        source_action is not None,
        f"Source action {source_cfg['expected_action']!r} not found.",
    )
    source_armature.animation_data_create()
    source_armature.animation_data.action = source_action

    frame_start = int(round(float(source_action.frame_range[0])))
    frame_end = int(round(float(source_action.frame_range[1])))
    frame_count = frame_end - frame_start + 1
    require(
        frame_count == int(source_cfg["expected_frame_count"]),
        f"Expected {source_cfg['expected_frame_count']} source frames; "
        f"found {frame_count}.",
    )

    marker_frames = {
        marker.name: int(marker.frame)
        for marker in scene.timeline_markers
    }
    labels = list(source_cfg["labels"])
    missing = [label for label in labels if label not in marker_frames]
    require(not missing, f"Source markers missing: {missing}")

    # Freeze the source as a visible ghost/reference. It remains animated, but
    # it is never connected to the target rig by drivers or constraints.
    source_objects = list(scene.objects)
    for obj in source_objects:
        obj["phase11_3_role"] = "source_visual_reference"
        if obj.type == "MESH":
            obj.display_type = "WIRE"
            obj.show_in_front = True
        elif obj.type == "ARMATURE":
            obj.show_in_front = True
            obj.display_type = "BBONE"

    target_cfg = contract["target"]
    target_path = repo / target_cfg["glb"]
    require(target_path.exists(), f"Target GLB missing: {target_path}")

    before_names = {obj.name for obj in bpy.data.objects}
    result = bpy.ops.import_scene.gltf(filepath=str(target_path))
    require("FINISHED" in result, f"Target GLB import failed: {result}")
    target_objects = [
        obj for obj in scene.objects if obj.name not in before_names
    ]
    target_armature = find_armature(target_cfg["expected_armature"])
    target_armature["phase11_3_role"] = "final_game_rig_authority"
    target_armature.show_in_front = True

    # Keep the two figures side by side for pose matching. This is layout only;
    # it is not animation data and creates no source->target transform mapping.
    source_min, source_max = scene_bounds(source_objects)
    target_min, target_max = scene_bounds(target_objects)
    source_width = max(source_max.x - source_min.x, 0.5)
    target_width = max(target_max.x - target_min.x, 0.5)
    gap = max(source_width, target_width) * 0.75
    shift_x = source_max.x + gap - target_min.x
    for obj in target_objects:
        if obj.parent is None:
            obj.location.x += shift_x

    bpy.context.view_layer.update()
    clear_target_pose(target_armature)

    # Remove any imported target animation assignment. The final-rig authored
    # stumble clip is the sole target animation authority in this lab.
    target_armature.animation_data_create()
    target_action = bpy.data.actions.get(ACTION_NAME)
    if target_action is None:
        target_action = bpy.data.actions.new(ACTION_NAME)
    target_armature.animation_data.action = target_action

    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.frame_set(frame_start)

    for label in labels:
        target_armature[f"marker_{label.lower().replace(' ', '_')}"] = marker_frames[label]

    scene["phase11_3_authoring_mode"] = "final_rig_direct"
    scene["phase11_3_source_role"] = "visual_reference_only"
    scene["phase11_3_target_action"] = ACTION_NAME

    # Contract guard: no source object is allowed to drive or constrain target.
    target_constraints = []
    for pb in target_armature.pose.bones:
        for constraint in pb.constraints:
            target_constraints.append((pb.name, constraint.name))
    require(
        not target_constraints,
        f"Target rig unexpectedly contains constraints: {target_constraints}",
    )

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "phase": PHASE,
        "mode": "final_rig_direct_authoring",
        "source": {
            "blend": str(source_blend),
            "armature": source_armature.name,
            "action": source_action.name,
            "frame_start": frame_start,
            "frame_end": frame_end,
            "frame_count": frame_count,
            "markers": {label: marker_frames[label] for label in labels},
            "role": "visual_reference_only",
        },
        "target": {
            "glb": target_cfg["glb"],
            "armature": target_armature.name,
            "action": ACTION_NAME,
            "role": "final_game_rig_authority",
            "layout_shift_x": round(float(shift_x), 6),
        },
        "policy": {
            "automated_retarget": False,
            "source_drives_target": False,
            "target_constraints_from_source": False,
            "key_pose_gate": labels,
            "breakdowns_after_key_pose_gate": True,
            "forward_root_translation": "gameplay_owned",
        },
    }

    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))

    print("")
    print("PHASE 11.3 FINAL-RIG AUTHORING LAB READY")
    print(f"Frames:  {frame_start}..{frame_end}")
    print(f"Source:  {source_armature.name} / {source_action.name}")
    print(f"Target:  {target_armature.name} / {ACTION_NAME}")
    print(f"Blend:   {output_blend}")
    print(f"Report:  {report_path}")


if __name__ == "__main__":
    main()
