#!/usr/bin/env python3
"""Phase 11.3 — direct final-rig key poses A.

Authors RUN -> TOE CATCH -> MOMENTUM FORWARD directly on low_poly_girl/Rig.
The source Runner_RIG is present in the lab only as a visual reference and is
never sampled for target transforms. Only the authored marker frame numbers are
reused as choreography timing.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PHASE = "11.3"
ACTION_NAME = "stumble_recovery_v1"
POSE_NAMES = ("RUN", "TOE CATCH", "MOMENTUM FORWARD")
TARGET_BONES = (
    "Hips", "Spine", "Spine 1", "Chest", "Neck", "Head",
    "Clavicle_L", "Clavicle_R",
    "Upper_Arm_L", "Lower_Arm_L", "Hand_L",
    "Upper_Arm_R", "Lower_Arm_R", "Hand_R",
    "Upper_Leg_L", "Lower_Leg_L", "Foot_L",
    "Upper_Leg_R", "Lower_Leg_R", "Foot_R",
    "Toes_L", "Toes_R",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--input-blend", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--report", required=True)
    return parser.parse_args(argv)


def load_phase10_core(repo: Path):
    core_path = repo / "tools/blender/build_opening_reverence_v1.py"
    spec = importlib.util.spec_from_file_location("phase10_pose_core", core_path)
    require(spec is not None and spec.loader is not None, "Cannot load pose core.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_axes(repo: Path) -> dict[str, Vector]:
    seed_path = (
        repo
        / "assets/characters/low_poly_girl/ballet_rig_calibration_seed_v1.json"
    )
    seed = json.loads(seed_path.read_text(encoding="utf-8"))
    declared = seed["declared_anatomical_frame"]
    return {
        "up": Vector(declared["up"]).normalized(),
        "side": Vector(declared["left"]).normalized(),
        "forward": Vector(declared["front"]).normalized(),
    }


def direction(
    axes: dict[str, Vector],
    *,
    side: float = 0.0,
    up: float = 0.0,
    forward: float = 0.0,
) -> Vector:
    value = (
        axes["side"] * side
        + axes["up"] * up
        + axes["forward"] * forward
    )
    require(value.length > 1e-8, "Authored direction is degenerate.")
    return value.normalized()


POSES = {
    "RUN": {
        "hips_drop_leg": 0.015,
        "spine_deg": 7.0,
        "chest_deg": 3.0,
        "head_deg": -2.0,
        "arms": {
            "L": {
                "upper": {"side": 0.10, "up": -0.34, "forward": 0.94},
                "lower": {"side": 0.05, "up": -0.20, "forward": 0.98},
                "hand": {"side": 0.02, "up": -0.08, "forward": 1.00},
            },
            "R": {
                "upper": {"side": -0.10, "up": -0.42, "forward": -0.90},
                "lower": {"side": -0.04, "up": 0.46, "forward": -0.89},
                "hand": {"side": -0.02, "up": 0.16, "forward": -0.99},
            },
        },
        "legs": {
            "R": {
                "upper": {"side": -0.03, "up": -0.78, "forward": 0.63},
                "lower": {"side": -0.02, "up": -0.86, "forward": 0.51},
                "foot": {"side": -0.02, "up": -0.10, "forward": 0.99},
            },
            "L": {
                "upper": {"side": 0.03, "up": -0.77, "forward": -0.64},
                "lower": {"side": 0.03, "up": 0.67, "forward": -0.74},
                "foot": {"side": 0.02, "up": -0.12, "forward": 0.99},
            },
        },
    },
    "TOE CATCH": {
        "hips_drop_leg": 0.045,
        "spine_deg": 13.0,
        "chest_deg": 5.0,
        "head_deg": -4.0,
        "arms": {
            "L": {
                "upper": {"side": 0.08, "up": -0.27, "forward": 0.96},
                "lower": {"side": 0.04, "up": -0.10, "forward": 0.99},
                "hand": {"side": 0.02, "up": -0.04, "forward": 1.00},
            },
            "R": {
                "upper": {"side": -0.08, "up": -0.30, "forward": 0.95},
                "lower": {"side": -0.04, "up": -0.12, "forward": 0.99},
                "hand": {"side": -0.02, "up": -0.04, "forward": 1.00},
            },
        },
        "legs": {
            "R": {
                "upper": {"side": -0.02, "up": -0.72, "forward": 0.69},
                "lower": {"side": -0.02, "up": -0.94, "forward": 0.34},
                "foot": {"side": -0.01, "up": -0.46, "forward": 0.89},
            },
            "L": {
                "upper": {"side": 0.03, "up": -0.83, "forward": -0.55},
                "lower": {"side": 0.03, "up": 0.55, "forward": -0.83},
                "foot": {"side": 0.02, "up": -0.08, "forward": 1.00},
            },
        },
    },
    "MOMENTUM FORWARD": {
        "hips_drop_leg": 0.080,
        "spine_deg": 23.0,
        "chest_deg": 8.0,
        "head_deg": -7.0,
        "arms": {
            "L": {
                "upper": {"side": 0.07, "up": -0.12, "forward": 0.99},
                "lower": {"side": 0.03, "up": 0.02, "forward": 1.00},
                "hand": {"side": 0.01, "up": 0.02, "forward": 1.00},
            },
            "R": {
                "upper": {"side": -0.07, "up": -0.14, "forward": 0.99},
                "lower": {"side": -0.03, "up": 0.00, "forward": 1.00},
                "hand": {"side": -0.01, "up": 0.02, "forward": 1.00},
            },
        },
        "legs": {
            "R": {
                "upper": {"side": -0.02, "up": -0.68, "forward": 0.73},
                "lower": {"side": -0.02, "up": -0.79, "forward": -0.61},
                "foot": {"side": -0.01, "up": -0.10, "forward": 0.99},
            },
            "L": {
                "upper": {"side": 0.03, "up": -0.91, "forward": 0.42},
                "lower": {"side": 0.03, "up": -0.88, "forward": 0.47},
                "foot": {"side": 0.02, "up": -0.08, "forward": 1.00},
            },
        },
    },
}


def apply_segment_chain(
    core,
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    bones: tuple[str, str, str],
    specs: dict,
    reference_normal: Vector,
) -> None:
    first, second, third = bones

    first_dir = direction(axes, **specs["upper"])
    second_dir = direction(axes, **specs["lower"])
    third_dir = direction(axes, **specs["hand"] if "hand" in specs else specs["foot"])

    first_len = (core.pose_tail(armature, first) - core.pose_head(armature, first)).length
    second_len = (core.pose_tail(armature, second) - core.pose_head(armature, second)).length
    third_len = (core.pose_tail(armature, third) - core.pose_head(armature, third)).length

    first_target = core.pose_head(armature, first) + first_dir * first_len
    plane = first_dir.cross(second_dir)
    if plane.length <= 1e-8:
        plane = reference_normal.copy()
    else:
        plane.normalize()
        if plane.dot(reference_normal) < 0.0:
            plane = -plane

    core.set_roll_stable_bone_frame(
        armature, first, first_target, plane, reference_normal
    )

    second_target = core.pose_head(armature, second) + second_dir * second_len
    core.set_roll_stable_bone_frame(
        armature, second, second_target, plane, reference_normal
    )

    third_target = core.pose_head(armature, third) + third_dir * third_len
    core.set_roll_stable_bone_frame(
        armature, third, third_target, plane, reference_normal
    )


def apply_pose(
    core,
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
    pose: dict,
) -> None:
    core.clear_pose(armature)

    upper_leg = core.joint_length(rest, "Upper_Leg_L", "Lower_Leg_L")
    lower_leg = core.joint_length(rest, "Lower_Leg_L", "Foot_L")
    leg = upper_leg + lower_leg

    core.translate_pose_bone_world(
        armature.pose.bones["Hips"],
        -axes["up"] * leg * float(pose["hips_drop_leg"]),
    )
    bpy.context.view_layer.update()

    core.rotate_pose_bone_world(
        armature.pose.bones["Spine 1"],
        axes["side"],
        float(pose["spine_deg"]),
    )
    bpy.context.view_layer.update()
    core.rotate_pose_bone_world(
        armature.pose.bones["Chest"],
        axes["side"],
        float(pose["chest_deg"]),
    )
    bpy.context.view_layer.update()
    core.rotate_pose_bone_world(
        armature.pose.bones["Head"],
        axes["side"],
        float(pose["head_deg"]),
    )
    bpy.context.view_layer.update()

    for suffix, sign in (("L", 1.0), ("R", -1.0)):
        apply_segment_chain(
            core,
            armature,
            axes,
            (
                f"Upper_Arm_{suffix}",
                f"Lower_Arm_{suffix}",
                f"Hand_{suffix}",
            ),
            pose["arms"][suffix],
            axes["side"] * sign,
        )

    for suffix, sign in (("L", 1.0), ("R", -1.0)):
        leg_spec = pose["legs"][suffix]
        normalized = {
            "upper": leg_spec["upper"],
            "lower": leg_spec["lower"],
            "foot": leg_spec["foot"],
        }
        apply_segment_chain(
            core,
            armature,
            axes,
            (
                f"Upper_Leg_{suffix}",
                f"Lower_Leg_{suffix}",
                f"Foot_{suffix}",
            ),
            normalized,
            axes["side"] * sign,
        )


def key_pose(armature: bpy.types.Object, frame: int) -> None:
    for bone_name in TARGET_BONES:
        pb = armature.pose.bones.get(bone_name)
        if pb is None:
            continue
        pb.rotation_mode = "QUATERNION"
        pb.keyframe_insert(
            data_path="rotation_quaternion",
            frame=frame,
            group=bone_name,
        )
        pb.keyframe_insert(
            data_path="location",
            frame=frame,
            group=bone_name,
        )


def choose_preview_engine(scene: bpy.types.Scene) -> str:
    prop = scene.render.bl_rna.properties["engine"]
    available = {item.identifier for item in prop.enum_items}
    for candidate in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "BLENDER_WORKBENCH"):
        if candidate in available:
            scene.render.engine = candidate
            return candidate
    raise RuntimeError(f"No supported preview engine: {sorted(available)}")


def configure_video_output(scene: bpy.types.Scene) -> str:
    image_settings = scene.render.image_settings
    media_property = image_settings.bl_rna.properties.get("media_type")
    if media_property is not None:
        values = {item.identifier for item in media_property.enum_items}
        if "VIDEO" in values:
            image_settings.media_type = "VIDEO"
            return "MEDIA_TYPE_VIDEO"

    format_property = image_settings.bl_rna.properties.get("file_format")
    if format_property is not None:
        values = {item.identifier for item in format_property.enum_items}
        if "FFMPEG" in values:
            image_settings.file_format = "FFMPEG"
            return "FILE_FORMAT_FFMPEG"

    raise RuntimeError("Blender video output API unavailable.")


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction_value = target - obj.location
    require(direction_value.length > 1e-8, "Preview camera direction is zero.")
    obj.rotation_euler = direction_value.to_track_quat("-Z", "Y").to_euler()


def configure_preview(
    core,
    scene: bpy.types.Scene,
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    preview_path: Path,
    frame_start: int,
    frame_end: int,
) -> tuple[str, str]:
    engine = choose_preview_engine(scene)
    video_api = configure_video_output(scene)

    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = 30
    scene.render.fps_base = 1.0
    scene.render.resolution_x = 720
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = str(preview_path)

    if scene.world is None:
        scene.world = bpy.data.worlds.new("Phase11_3_FinalRigWorld")
    scene.world.use_nodes = True
    bg = scene.world.node_tree.nodes.get("Background")
    if bg is not None:
        bg.inputs["Color"].default_value = (0.91, 0.92, 0.94, 1.0)
        bg.inputs["Strength"].default_value = 0.85

    # Preview only the final game rig. Source reference remains in the .blend.
    for obj in scene.objects:
        if obj.get("phase11_3_role") == "source_visual_reference":
            obj.hide_render = True

    scene.frame_set(frame_start)
    bpy.context.view_layer.update()
    hips = core.pose_head(armature, "Hips")
    head = core.pose_head(armature, "Head")
    center_local = (hips + head) * 0.5
    center_world = armature.matrix_world @ center_local

    side_world = (
        armature.matrix_world.to_3x3() @ axes["side"]
    ).normalized()
    up_world = (
        armature.matrix_world.to_3x3() @ axes["up"]
    ).normalized()

    body_height = max((head - hips).length * 2.35, 1.5)
    camera_data = bpy.data.cameras.new("Phase11_3_KeyposesA_Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = body_height
    camera = bpy.data.objects.new("Phase11_3_KeyposesA_Camera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center_world + side_world * body_height * 2.2
    look_at(camera, center_world)
    scene.camera = camera

    for name, offset, energy in (
        (
            "Phase11_3_Key",
            side_world * body_height + up_world * body_height * 0.9,
            950.0,
        ),
        (
            "Phase11_3_Fill",
            -side_world * body_height + up_world * body_height * 0.35,
            500.0,
        ),
    ):
        data = bpy.data.lights.new(name=name, type="AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = body_height
        light = bpy.data.objects.new(name, data)
        scene.collection.objects.link(light)
        light.location = center_world + offset
        look_at(light, center_world)

    return engine, video_api


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    input_blend = Path(args.input_blend).resolve()
    output_blend = Path(args.output_blend).resolve()
    preview_path = Path(args.preview).resolve()
    report_path = Path(args.report).resolve()

    require(input_blend.exists(), f"Authoring lab missing: {input_blend}")
    bpy.ops.wm.open_mainfile(filepath=str(input_blend))
    scene = bpy.context.scene
    require(
        scene.get("phase11_3_authoring_mode") == "final_rig_direct",
        "Input is not a Phase 11.3 final-rig direct authoring lab.",
    )

    core = load_phase10_core(repo)
    axes = load_axes(repo)
    armature = bpy.data.objects.get("Rig")
    require(
        armature is not None and armature.type == "ARMATURE",
        "Target Rig not found.",
    )

    # The source armature is timing/reference only. No source pose data is read.
    source = bpy.data.objects.get("Runner_RIG")
    require(source is not None, "Source visual reference missing.")

    marker_frames = {}
    for pose_name in POSE_NAMES:
        prop_name = f"marker_{pose_name.lower().replace(' ', '_')}"
        require(prop_name in armature, f"Missing marker property {prop_name}.")
        marker_frames[pose_name] = int(armature[prop_name])

    require(
        list(marker_frames.values()) == sorted(marker_frames.values()),
        f"Key pose frames are not chronological: {marker_frames}",
    )

    rest = core.rest_snapshot(armature)
    armature.animation_data_create()
    action = bpy.data.actions.get(ACTION_NAME)
    if action is None:
        action = bpy.data.actions.new(ACTION_NAME)
    armature.animation_data.action = action

    # Start this bounded authored pass from an empty target action.
    if hasattr(action, "fcurves"):
        for curve in list(action.fcurves):
            action.fcurves.remove(curve)

    for pose_name in POSE_NAMES:
        frame = marker_frames[pose_name]
        scene.frame_set(frame)
        apply_pose(core, armature, axes, rest, POSES[pose_name])
        key_pose(armature, frame)

    if hasattr(action, "fcurves"):
        for curve in action.fcurves:
            for key in curve.keyframe_points:
                key.interpolation = "BEZIER"
                key.handle_left_type = "AUTO_CLAMPED"
                key.handle_right_type = "AUTO_CLAMPED"

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    engine, video_api = configure_preview(
        core,
        scene,
        armature,
        axes,
        preview_path,
        marker_frames["RUN"],
        marker_frames["MOMENTUM FORWARD"],
    )

    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))
    bpy.ops.render.render(animation=True)

    report = {
        "phase": PHASE,
        "mode": "final_rig_direct_keyposes_a",
        "action": ACTION_NAME,
        "poses": [
            {"name": name, "frame": marker_frames[name]}
            for name in POSE_NAMES
        ],
        "source_transform_sampling": False,
        "target_armature": armature.name,
        "preview": {
            "path": str(preview_path),
            "engine": engine,
            "video_api": video_api,
        },
        "next_gate": "human_visual_review_before_peak_stumble",
    }
    report_path.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    print("")
    print("PHASE 11.3 FINAL-RIG KEYPOSES A PASS")
    for name in POSE_NAMES:
        print(f"{name}: {marker_frames[name]}")
    print(f"Blend:   {output_blend}")
    print(f"Preview: {preview_path}")
    print(f"Report:  {report_path}")


if __name__ == "__main__":
    main()
