#!/usr/bin/env python3
"""Phase 10.4.1 — programmatic authored opening reverence pipeline."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler


ACTION_NAME = "Opening_Reverence_v1"
FPS = 30
END_FRAME = 68

REQUIRED_BONES = [
    "Hips", "Spine", "Spine 1", "Chest", "Neck", "Head",
    "Clavicle_L", "Clavicle_R",
    "Upper_Arm_L", "Upper_Arm_R",
    "Lower_Arm_L", "Lower_Arm_R",
    "Hand_L", "Hand_R", "Middle_L", "Middle_R",
    "Upper_Leg_L", "Upper_Leg_R",
    "Lower_Leg_L", "Lower_Leg_R",
    "Foot_L", "Foot_R", "Toes_L", "Toes_R",
]

POSES = [
    {"frame": 1, "name": "READY", "rot": {}, "loc": {}},
    {
        "frame": 9, "name": "BRAS_BAS",
        "rot": {
            "Clavicle_L": (0.0, 0.0, 1.5), "Clavicle_R": (0.0, 0.0, -1.5),
            "Upper_Arm_L": (0.0, 0.0, 6.0), "Upper_Arm_R": (0.0, 0.0, -6.0),
            "Lower_Arm_L": (0.0, 0.0, -14.0), "Lower_Arm_R": (0.0, 0.0, 14.0),
            "Hand_L": (0.0, 0.0, -4.0), "Hand_R": (0.0, 0.0, 4.0),
        }, "loc": {},
    },
    {
        "frame": 20, "name": "EN_AVANT_PASSAGE",
        "rot": {
            "Clavicle_L": (0.0, 0.0, 2.5), "Clavicle_R": (0.0, 0.0, -2.5),
            "Upper_Arm_L": (0.0, 0.0, 12.0), "Upper_Arm_R": (0.0, 0.0, -12.0),
            "Lower_Arm_L": (0.0, 0.0, -28.0), "Lower_Arm_R": (0.0, 0.0, 28.0),
            "Hand_L": (0.0, 0.0, -6.0), "Hand_R": (0.0, 0.0, 6.0),
        }, "loc": {},
    },
    {
        "frame": 32, "name": "PLACEMENT_AND_SOFTEN",
        "rot": {
            "Clavicle_L": (0.0, 0.0, 3.0), "Clavicle_R": (0.0, 0.0, -3.0),
            "Upper_Arm_L": (0.0, 0.0, 8.0), "Upper_Arm_R": (0.0, 0.0, -8.0),
            "Lower_Arm_L": (0.0, 0.0, -20.0), "Lower_Arm_R": (0.0, 0.0, 20.0),
            "Lower_Leg_L": (10.0, 0.0, 0.0), "Lower_Leg_R": (10.0, 0.0, 0.0),
            "Spine 1": (2.0, 0.0, 0.0),
        }, "loc": {"Hips": (0.0, 0.0, -0.025)},
    },
    {
        "frame": 40, "name": "ACKNOWLEDGEMENT",
        "rot": {
            "Clavicle_L": (0.0, 0.0, 2.0), "Clavicle_R": (0.0, 0.0, -2.0),
            "Upper_Arm_L": (0.0, 0.0, 4.0), "Upper_Arm_R": (0.0, 0.0, -4.0),
            "Lower_Arm_L": (0.0, 0.0, -10.0), "Lower_Arm_R": (0.0, 0.0, 10.0),
            "Lower_Leg_L": (14.0, 0.0, 0.0), "Lower_Leg_R": (14.0, 0.0, 0.0),
            "Spine 1": (4.0, 0.0, 0.0), "Chest": (2.0, 0.0, 0.0), "Head": (4.0, 0.0, 0.0),
        }, "loc": {"Hips": (0.0, 0.0, -0.045)},
    },
    {
        "frame": 52, "name": "RISE_AND_OPEN",
        "rot": {
            "Clavicle_L": (0.0, 0.0, 1.5), "Clavicle_R": (0.0, 0.0, -1.5),
            "Upper_Arm_L": (0.0, 0.0, -3.0), "Upper_Arm_R": (0.0, 0.0, 3.0),
            "Lower_Arm_L": (0.0, 0.0, -4.0), "Lower_Arm_R": (0.0, 0.0, 4.0),
            "Lower_Leg_L": (4.0, 0.0, 0.0), "Lower_Leg_R": (4.0, 0.0, 0.0),
            "Spine 1": (1.0, 0.0, 0.0), "Head": (1.0, 0.0, 0.0),
        }, "loc": {"Hips": (0.0, 0.0, -0.012)},
    },
    {"frame": END_FRAME, "name": "READY_RESOLUTION", "rot": {}, "loc": {}},
]


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--blend-output")
    return parser.parse_args(argv)


def vec3(v) -> list[float]:
    return [round(float(v[0]), 6), round(float(v[1]), 6), round(float(v[2]), 6)]


def action_summary(action: bpy.types.Action) -> dict:
    frame_range = tuple(float(x) for x in action.frame_range)
    return {
        "name": action.name,
        "frame_start": round(frame_range[0], 3),
        "frame_end": round(frame_range[1], 3),
    }


def find_armature() -> bpy.types.Object:
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"]
    if not armatures:
        raise RuntimeError("No Armature object found after GLB import.")
    for obj in armatures:
        if obj.name == "Rig":
            return obj
    return armatures[0]


def clear_pose(armature: bpy.types.Object) -> None:
    for pb in armature.pose.bones:
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.location = (0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def set_rotation_deg(pb: bpy.types.PoseBone, degrees_xyz) -> None:
    radians_xyz = tuple(math.radians(float(v)) for v in degrees_xyz)
    pb.rotation_mode = "QUATERNION"
    pb.rotation_quaternion = Euler(radians_xyz, "XYZ").to_quaternion()


def key_pose(armature: bpy.types.Object, pose: dict) -> None:
    clear_pose(armature)
    for bone_name, rot in pose["rot"].items():
        set_rotation_deg(armature.pose.bones[bone_name], rot)
    for bone_name, loc in pose["loc"].items():
        armature.pose.bones[bone_name].location = tuple(float(v) for v in loc)

    bpy.context.view_layer.update()
    frame = int(pose["frame"])
    for bone_name in REQUIRED_BONES:
        pb = armature.pose.bones[bone_name]
        pb.keyframe_insert(data_path="rotation_quaternion", frame=frame, group=bone_name)
        pb.keyframe_insert(data_path="location", frame=frame, group=bone_name)


def configure_interpolation(action: bpy.types.Action) -> None:
    fcurves = getattr(action, "fcurves", None)
    if fcurves is None:
        return
    for fcurve in fcurves:
        for point in fcurve.keyframe_points:
            point.interpolation = "BEZIER"
            point.handle_left_type = "AUTO_CLAMPED"
            point.handle_right_type = "AUTO_CLAMPED"


def export_glb(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    kwargs = {"filepath": str(output_path), "export_format": "GLB", "export_animations": True}
    optional = {
        "export_animation_mode": "ACTIONS",
        "export_force_sampling": True,
        "export_frame_step": 1,
        "export_rest_position_armature": False,
    }
    for key, value in optional.items():
        if key in props:
            kwargs[key] = value
    result = bpy.ops.export_scene.gltf(**kwargs)
    if "FINISHED" not in result:
        raise RuntimeError(f"glTF export did not finish: {result}")


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    report_path = Path(args.report).resolve()
    blend_output = Path(args.blend_output).resolve() if args.blend_output else None

    if not input_path.exists():
        raise FileNotFoundError(input_path)
    if input_path == output_path:
        raise RuntimeError("Refusing to overwrite the source GLB.")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    result = bpy.ops.import_scene.gltf(filepath=str(input_path))
    if "FINISHED" not in result:
        raise RuntimeError(f"glTF import did not finish: {result}")

    armature = find_armature()
    missing = [name for name in REQUIRED_BONES if name not in armature.pose.bones]
    if missing:
        raise RuntimeError(f"Audited ballet rig contract missing bones: {missing}")

    actions_before = [action_summary(a) for a in bpy.data.actions]

    if ACTION_NAME in bpy.data.actions:
        bpy.data.actions.remove(bpy.data.actions[ACTION_NAME])

    action = bpy.data.actions.new(ACTION_NAME)
    action.use_fake_user = True
    armature.animation_data_create()
    armature.animation_data.action = action

    bpy.context.scene.render.fps = FPS
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = END_FRAME

    for pose in POSES:
        key_pose(armature, pose)

    configure_interpolation(action)
    bpy.context.scene.frame_set(1)

    if blend_output is not None:
        blend_output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_output))

    export_glb(output_path)

    axes = {}
    for bone_name in REQUIRED_BONES:
        bone = armature.data.bones[bone_name]
        basis = bone.matrix_local.to_3x3()
        axes[bone_name] = {
            "head_local": vec3(bone.head_local),
            "tail_local": vec3(bone.tail_local),
            "axis_x": vec3(basis.col[0]),
            "axis_y_length": vec3(basis.col[1]),
            "axis_z": vec3(basis.col[2]),
            "parent": bone.parent.name if bone.parent else None,
        }

    report = {
        "phase": "10.4.1",
        "source_glb": str(input_path),
        "output_glb": str(output_path),
        "blend_output": str(blend_output) if blend_output else None,
        "armature": armature.name,
        "fps": FPS,
        "end_frame": END_FRAME,
        "duration_seconds": round((END_FRAME - 1) / FPS, 4),
        "required_bones_ok": True,
        "actions_before": actions_before,
        "actions_after": [action_summary(a) for a in bpy.data.actions],
        "authored_action": ACTION_NAME,
        "poses": [{"frame": p["frame"], "name": p["name"]} for p in POSES],
        "bone_axes": axes,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("PHASE10_4_1=PASS")
    print(f"ARMATURE={armature.name}")
    print(f"ACTION={ACTION_NAME}")
    print(f"OUTPUT={output_path}")
    print(f"REPORT={report_path}")


if __name__ == "__main__":
    main()
