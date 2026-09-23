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
        "hips_drop_leg": 0.010,
        "spine_deg": 5.0,
        "chest_deg": 2.0,
        "head_deg": 0.0,
        "arms": {
            # Compact runner arms: hands stay below the chest, not near face.
            "L": {
                "elbow": {"side": 0.05, "up": -0.24, "forward": 0.27},
                "wrist": {"side": 0.03, "up": -0.34, "forward": 0.10},
            },
            "R": {
                "elbow": {"side": -0.05, "up": -0.25, "forward": -0.25},
                "wrist": {"side": -0.03, "up": -0.37, "forward": -0.07},
            },
        },
        "legs": {
            "R": {
                "knee": {"side": -0.02, "up": -0.45, "forward": 0.26},
                "ankle": {"side": -0.01, "up": -0.83, "forward": 0.42},
                "finish": {"side": -0.01, "up": -0.85, "forward": 0.53},
            },
            "L": {
                "knee": {"side": 0.02, "up": -0.43, "forward": -0.16},
                "ankle": {"side": 0.01, "up": -0.69, "forward": -0.24},
                "finish": {"side": 0.01, "up": -0.70, "forward": -0.12},
            },
        },
    },
    "TOE CATCH": {
        "hips_drop_leg": 0.040,
        "spine_deg": 12.0,
        "chest_deg": 4.0,
        "head_deg": -1.0,
        "arms": {
            # Reflex starts asymmetrically; hands remain around lower chest.
            "L": {
                "elbow": {"side": 0.06, "up": -0.22, "forward": 0.30},
                "wrist": {"side": 0.04, "up": -0.29, "forward": 0.18},
            },
            "R": {
                "elbow": {"side": -0.06, "up": -0.27, "forward": -0.05},
                "wrist": {"side": -0.04, "up": -0.34, "forward": 0.12},
            },
        },
        "legs": {
            # Right toe is arrested ahead and close to the floor.
            "R": {
                "knee": {"side": -0.02, "up": -0.49, "forward": 0.31},
                "ankle": {"side": -0.01, "up": -0.87, "forward": 0.46},
                "finish": {"side": -0.01, "up": -0.92, "forward": 0.53},
            },
            # Rear leg folds and begins to come through.
            "L": {
                "knee": {"side": 0.02, "up": -0.47, "forward": -0.10},
                "ankle": {"side": 0.01, "up": -0.70, "forward": -0.16},
                "finish": {"side": 0.01, "up": -0.71, "forward": -0.04},
            },
        },
    },
    "MOMENTUM FORWARD": {
        "hips_drop_leg": 0.075,
        "spine_deg": 25.0,
        "chest_deg": 6.0,
        "head_deg": -1.0,
        "arms": {
            # Protective reflex forward, but elbows remain bent and hands stay
            # below shoulder height instead of forming a face-covering pose.
            "L": {
                "elbow": {"side": 0.08, "up": -0.18, "forward": 0.31},
                "wrist": {"side": 0.05, "up": -0.20, "forward": 0.43},
            },
            "R": {
                "elbow": {"side": -0.08, "up": -0.22, "forward": 0.24},
                "wrist": {"side": -0.05, "up": -0.25, "forward": 0.36},
            },
        },
        "legs": {
            # Caught leg buckles under the pitching body.
            "R": {
                "knee": {"side": -0.02, "up": -0.57, "forward": 0.24},
                "ankle": {"side": -0.01, "up": -0.89, "forward": 0.38},
                "finish": {"side": -0.01, "up": -0.91, "forward": 0.49},
            },
            # Left leg begins the emergency catch step, without crossing wildly.
            "L": {
                "knee": {"side": 0.02, "up": -0.47, "forward": 0.06},
                "ankle": {"side": 0.01, "up": -0.70, "forward": -0.03},
                "finish": {"side": 0.01, "up": -0.71, "forward": 0.09},
            },
        },
    },
}

def authored_point(
    root: Vector,
    axes: dict[str, Vector],
    scale: float,
    spec: dict,
) -> Vector:
    return (
        root
        + axes["side"] * scale * float(spec["side"])
        + axes["up"] * scale * float(spec["up"])
        + axes["forward"] * scale * float(spec["forward"])
    )


def apply_landmark_chain(
    core,
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    bones: tuple[str, str, str],
    specs: dict,
    labels: tuple[str, str],
    scale: float,
    reference_normal: Vector,
    preserve_third_rest: bool,
) -> None:
    first, second, third = bones
    first_label, second_label = labels

    root = core.pose_head(armature, first).copy()
    first_target = authored_point(
        root, axes, scale, specs[first_label]
    )
    second_target = authored_point(
        root, axes, scale, specs[second_label]
    )

    upper_direction = first_target - root
    lower_direction = second_target - first_target
    plane = upper_direction.cross(lower_direction)
    if plane.length <= 1e-8:
        plane = reference_normal.copy()
    else:
        plane.normalize()
        if plane.dot(reference_normal) < 0.0:
            plane = -plane

    core.set_roll_stable_bone_frame(
        armature,
        first,
        first_target,
        plane,
        reference_normal,
    )
    core.set_roll_stable_bone_frame(
        armature,
        second,
        second_target,
        plane,
        reference_normal,
    )

    if not preserve_third_rest:
        finish_target = authored_point(
            root, axes, scale, specs["finish"]
        )
        core.set_roll_stable_bone_frame(
            armature,
            third,
            finish_target,
            plane,
            reference_normal,
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
        arm_reach = (
            core.joint_length(
                rest,
                f"Upper_Arm_{suffix}",
                f"Lower_Arm_{suffix}",
            )
            + core.joint_length(
                rest,
                f"Lower_Arm_{suffix}",
                f"Hand_{suffix}",
            )
        )
        apply_landmark_chain(
            core,
            armature,
            axes,
            (
                f"Upper_Arm_{suffix}",
                f"Lower_Arm_{suffix}",
                f"Hand_{suffix}",
            ),
            pose["arms"][suffix],
            ("elbow", "wrist"),
            arm_reach,
            axes["side"] * sign,
            True,
        )

    for suffix, sign in (("L", 1.0), ("R", -1.0)):
        leg_reach = (
            core.joint_length(
                rest,
                f"Upper_Leg_{suffix}",
                f"Lower_Leg_{suffix}",
            )
            + core.joint_length(
                rest,
                f"Lower_Leg_{suffix}",
                f"Foot_{suffix}",
            )
        )
        apply_landmark_chain(
            core,
            armature,
            axes,
            (
                f"Upper_Leg_{suffix}",
                f"Lower_Leg_{suffix}",
                f"Foot_{suffix}",
            ),
            pose["legs"][suffix],
            ("knee", "ankle"),
            leg_reach,
            axes["side"] * sign,
            False,
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
