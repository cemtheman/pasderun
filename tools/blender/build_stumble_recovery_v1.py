"""Pas de Run — Phase 11.3 authored stumble/recovery retarget preview.

This tool treats the supplied Blender file as the authored motion authority.
It samples Runner_RIGAction frame-by-frame, transfers armature-space rest
rotation deltas into the declared low_poly_girl anatomical frame, removes
forward root translation, and builds a new low_poly_girl action for visual
review. It does not modify gameplay code or the production GLB.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


PHASE = "11.3"
ACTION_NAME = "stumble_recovery_v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--source-blend", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--output-blend", required=True)
    parser.add_argument("--preview", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--skip-render", action="store_true")
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unit(value: Vector, label: str) -> Vector:
    vector = value.copy()
    if vector.length <= 1e-8:
        raise RuntimeError(f"{label} is degenerate.")
    vector.normalize()
    return vector


def orthogonalized(value: Vector, against: Vector, label: str) -> Vector:
    result = value - against * value.dot(against)
    return unit(result, label)


def basis_columns(left: Vector, up: Vector, front: Vector) -> Matrix:
    # mathutils.Matrix is row-major when constructed from tuples.
    return Matrix(
        (
            (left.x, up.x, front.x),
            (left.y, up.y, front.y),
            (left.z, up.z, front.z),
        )
    )


def declared_target_frame(seed: dict) -> dict[str, Vector]:
    declared = seed["declared_anatomical_frame"]
    up = unit(Vector(declared["up"]), "target up")
    left = orthogonalized(Vector(declared["left"]), up, "target left")
    front = unit(left.cross(up), "target front")
    declared_front = unit(Vector(declared["front"]), "declared target front")
    require(
        front.dot(declared_front) >= 0.999,
        "Target frame handedness does not match declared calibration seed.",
    )
    return {"left": left, "up": up, "front": front}


def source_frame(armature: bpy.types.Object) -> tuple[dict[str, Vector], dict]:
    bones = armature.data.bones
    required = {"pelvis", "head", "thigh.L", "thigh.R", "foot.L", "foot.R"}
    missing = sorted(required - set(bones.keys()))
    require(not missing, f"Source frame bones missing: {missing}")

    up = unit(
        bones["head"].head_local - bones["pelvis"].head_local,
        "source up",
    )
    anatomical_left = (
        bones["thigh.L"].head_local - bones["thigh.R"].head_local
    )
    left = orthogonalized(anatomical_left, up, "source left")
    front = unit(left.cross(up), "source front")

    foot_forward = Vector((0.0, 0.0, 0.0))
    for name in ("foot.L", "foot.R"):
        foot_forward += unit(
            bones[name].tail_local - bones[name].head_local,
            f"{name} length",
        )
    foot_alignment = 0.0
    if foot_forward.length > 1e-8:
        foot_forward.normalize()
        foot_alignment = float(foot_forward.dot(front))

    evidence = {
        "up": [float(v) for v in up],
        "left": [float(v) for v in left],
        "front": [float(v) for v in front],
        "average_foot_front_alignment": round(foot_alignment, 8),
        "left_label_alignment": round(
            unit(anatomical_left, "source anatomical left").dot(left),
            8,
        ),
    }
    return {"left": left, "up": up, "front": front}, evidence


def find_armature(expected_name: str) -> bpy.types.Object:
    armatures = [
        obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE"
    ]
    for armature in armatures:
        if armature.name == expected_name:
            return armature
    raise RuntimeError(
        f"Expected armature {expected_name!r}; found "
        f"{sorted(obj.name for obj in armatures)}."
    )


def average_leg_length(
    armature: bpy.types.Object,
    thigh_names: tuple[str, str],
    shin_names: tuple[str, str],
) -> float:
    lengths = []
    for thigh, shin in zip(thigh_names, shin_names, strict=True):
        require(thigh in armature.data.bones, f"Missing bone {thigh}.")
        require(shin in armature.data.bones, f"Missing bone {shin}.")
        lengths.append(
            float(armature.data.bones[thigh].length)
            + float(armature.data.bones[shin].length)
        )
    return sum(lengths) / len(lengths)


def matrix_list(matrix: Matrix) -> list[list[float]]:
    return [
        [round(float(matrix[row][col]), 8) for col in range(4)]
        for row in range(4)
    ]


def sample_source(
    source_path: Path,
    contract: dict,
) -> dict:
    bpy.ops.wm.open_mainfile(filepath=str(source_path))

    source_cfg = contract["source"]
    armature = find_armature(source_cfg["expected_armature"])
    action = None
    if (
        armature.animation_data is not None
        and armature.animation_data.action is not None
        and armature.animation_data.action.name == source_cfg["expected_action"]
    ):
        action = armature.animation_data.action
    if action is None:
        action = bpy.data.actions.get(source_cfg["expected_action"])
    require(action is not None, f"Source action {source_cfg['expected_action']!r} not found.")

    armature.animation_data_create()
    armature.animation_data.action = action

    frame_start = int(round(float(action.frame_range[0])))
    frame_end = int(round(float(action.frame_range[1])))
    frame_count = frame_end - frame_start + 1
    require(
        frame_count == int(source_cfg["expected_frame_count"]),
        f"Expected {source_cfg['expected_frame_count']} source frames; "
        f"found {frame_count} ({frame_start}..{frame_end}).",
    )

    timeline_markers = {
        marker.name: int(marker.frame)
        for marker in bpy.context.scene.timeline_markers
    }
    expected_labels = list(source_cfg.get("labels", []))
    missing_labels = [
        label for label in expected_labels
        if label not in timeline_markers
    ]
    require(
        not missing_labels,
        f"Source authored phase markers missing: {missing_labels}",
    )
    marker_frames = [timeline_markers[label] for label in expected_labels]
    require(
        marker_frames == sorted(marker_frames),
        f"Source authored phase markers are not chronological: "
        f"{dict(zip(expected_labels, marker_frames, strict=True))}",
    )
    require(
        all(frame_start <= frame <= frame_end for frame in marker_frames),
        "One or more authored phase markers fall outside the action range.",
    )

    source_bones = sorted(contract["retarget"]["source_to_target"].keys())
    missing = sorted(
        bone for bone in source_bones if bone not in armature.pose.bones
    )
    require(not missing, f"Source retarget bones missing: {missing}")

    frame, frame_evidence = source_frame(armature)
    frame_basis = basis_columns(frame["left"], frame["up"], frame["front"])

    rest_rotations = {
        name: armature.data.bones[name].matrix_local.to_3x3().normalized().copy()
        for name in source_bones
    }

    scene = bpy.context.scene
    source_fps = float(scene.render.fps) / max(float(scene.render.fps_base), 1e-8)
    samples: list[dict] = []
    pelvis_start = None

    for frame_number in range(frame_start, frame_end + 1):
        scene.frame_set(frame_number)
        bpy.context.view_layer.update()
        pose_matrices = {
            name: armature.pose.bones[name].matrix.copy()
            for name in source_bones
        }
        pelvis_position = pose_matrices["pelvis"].translation.copy()
        if pelvis_start is None:
            pelvis_start = pelvis_position.copy()

        samples.append(
            {
                "source_frame": frame_number,
                "pose_matrices": pose_matrices,
                "pelvis_delta": pelvis_position - pelvis_start,
            }
        )

    source_leg_length = average_leg_length(
        armature,
        ("thigh.L", "thigh.R"),
        ("shin.L", "shin.R"),
    )

    return {
        "armature_name": armature.name,
        "action_name": action.name,
        "frame_start": frame_start,
        "frame_end": frame_end,
        "frame_count": frame_count,
        "fps": source_fps,
        "timeline_markers": {
            label: timeline_markers[label]
            for label in expected_labels
        },
        "frame": frame,
        "frame_basis": frame_basis,
        "frame_evidence": frame_evidence,
        "rest_rotations": rest_rotations,
        "samples": samples,
        "leg_length": source_leg_length,
    }


def clear_pose(armature: bpy.types.Object) -> None:
    for pose_bone in armature.pose.bones:
        pose_bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def target_depth(armature: bpy.types.Object, name: str) -> int:
    depth = 0
    bone = armature.data.bones[name]
    while bone.parent is not None:
        depth += 1
        bone = bone.parent
    return depth


def fraction_rotation(rotation: Matrix, weight: float) -> Matrix:
    weight = min(max(float(weight), 0.0), 1.0)
    if weight >= 0.999999:
        return rotation.copy()
    quaternion = rotation.to_quaternion().normalized()
    if quaternion.w < 0.0:
        quaternion = Quaternion(
            (-quaternion.w, -quaternion.x, -quaternion.y, -quaternion.z)
        )
    return Quaternion((1.0, 0.0, 0.0, 0.0)).slerp(
        quaternion,
        weight,
    ).to_matrix()


def set_pose_matrix(
    armature: bpy.types.Object,
    bone_name: str,
    rotation: Matrix,
    translation: Vector | None = None,
) -> None:
    pose_bone = armature.pose.bones[bone_name]
    current = pose_bone.matrix.copy()
    desired = Matrix.Identity(4)
    for row in range(3):
        for col in range(3):
            desired[row][col] = rotation[row][col]
    desired.translation = current.translation if translation is None else translation
    pose_bone.matrix = desired
    bpy.context.view_layer.update()


def retarget_to_low_poly(
    repo: Path,
    contract: dict,
    source: dict,
) -> tuple[bpy.types.Object, bpy.types.Action, dict]:
    bpy.ops.wm.read_factory_settings(use_empty=True)

    target_cfg = contract["target"]
    target_path = repo / target_cfg["glb"]
    require(target_path.exists(), f"Target GLB missing: {target_path}")

    result = bpy.ops.import_scene.gltf(filepath=str(target_path))
    require("FINISHED" in result, f"Target GLB import failed: {result}")
    armature = find_armature(target_cfg["expected_armature"])

    seed = json.loads(
        (repo / target_cfg["calibration_seed"]).read_text(encoding="utf-8")
    )
    target_frame = declared_target_frame(seed)
    source_basis = source["frame_basis"]
    target_basis = basis_columns(
        target_frame["left"],
        target_frame["up"],
        target_frame["front"],
    )
    source_to_target = target_basis @ source_basis.transposed()

    target_leg_length = average_leg_length(
        armature,
        ("Upper_Leg_L", "Upper_Leg_R"),
        ("Lower_Leg_L", "Lower_Leg_R"),
    )
    leg_ratio = target_leg_length / source["leg_length"]

    mapping: dict[str, list[str]] = contract["retarget"]["source_to_target"]
    required_targets = sorted({name for names in mapping.values() for name in names})
    missing_targets = sorted(
        name for name in required_targets if name not in armature.pose.bones
    )
    require(not missing_targets, f"Target retarget bones missing: {missing_targets}")

    target_rest_rotations = {
        name: armature.data.bones[name].matrix_local.to_3x3().normalized().copy()
        for name in required_targets
    }
    target_rest_hips = armature.data.bones["Hips"].matrix_local.translation.copy()

    # Imported native actions are kept in bpy.data for inspection, but this
    # armature is assigned only the authored stumble/recovery action.
    armature.animation_data_create()
    action = bpy.data.actions.new(ACTION_NAME)
    armature.animation_data.action = action

    spine_weights = contract["retarget"]["spine_distribution"]
    assignments: list[tuple[str, str, float]] = []
    for source_name, targets in mapping.items():
        for target_name in targets:
            weight = (
                float(spine_weights[target_name])
                if source_name == "spine"
                else 1.0
            )
            assignments.append((source_name, target_name, weight))
    assignments.sort(key=lambda item: target_depth(armature, item[1]))

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = source["frame_count"]
    fps_rounded = max(int(round(source["fps"])), 1)
    scene.render.fps = fps_rounded
    scene.render.fps_base = 1.0

    source_up = source["frame"]["up"]
    source_left = source["frame"]["left"]
    source_front = source["frame"]["front"]

    for out_index, sample in enumerate(source["samples"], start=1):
        scene.frame_set(out_index)
        clear_pose(armature)

        root_delta = sample["pelvis_delta"]
        body_root = Vector(
            (
                root_delta.dot(source_left),
                root_delta.dot(source_up),
                root_delta.dot(source_front),
            )
        )
        # Gameplay remains the forward-motion authority. Preserve authored
        # vertical/lateral COM response but remove forward root translation.
        body_root.z = 0.0
        mapped_root = (
            target_frame["left"] * body_root.x
            + target_frame["up"] * body_root.y
            + target_frame["front"] * body_root.z
        ) * leg_ratio
        hips_translation = target_rest_hips + mapped_root

        for source_name, target_name, weight in assignments:
            source_pose_rotation = (
                sample["pose_matrices"][source_name]
                .to_3x3()
                .normalized()
            )
            source_rest_rotation = source["rest_rotations"][source_name]
            source_delta = (
                source_pose_rotation @ source_rest_rotation.transposed()
            )
            target_delta = (
                source_to_target
                @ source_delta
                @ source_to_target.transposed()
            )
            target_delta = fraction_rotation(target_delta, weight)
            desired_rotation = (
                target_delta @ target_rest_rotations[target_name]
            )

            translation = hips_translation if target_name == "Hips" else None
            set_pose_matrix(
                armature,
                target_name,
                desired_rotation,
                translation,
            )

        for target_name in required_targets:
            pose_bone = armature.pose.bones[target_name]
            pose_bone.rotation_mode = "QUATERNION"
            pose_bone.keyframe_insert(
                data_path="rotation_quaternion",
                frame=out_index,
                group=target_name,
            )
            if target_name == "Hips":
                pose_bone.keyframe_insert(
                    data_path="location",
                    frame=out_index,
                    group=target_name,
                )

    # Every source frame is sampled, so LINEAR interpolation preserves the
    # authored frame sequence without Bezier overshoot.
    if hasattr(action, "fcurves"):
        for curve in action.fcurves:
            for keyframe in curve.keyframe_points:
                keyframe.interpolation = "LINEAR"

    report = {
        "phase": PHASE,
        "action": ACTION_NAME,
        "source": {
            "armature": source["armature_name"],
            "action": source["action_name"],
            "frame_start": source["frame_start"],
            "frame_end": source["frame_end"],
            "frame_count": source["frame_count"],
            "fps": round(source["fps"], 6),
            "timeline_markers": source["timeline_markers"],
            "leg_length": round(source["leg_length"], 8),
            "frame_evidence": source["frame_evidence"],
        },
        "target": {
            "armature": armature.name,
            "glb": target_cfg["glb"],
            "leg_length": round(target_leg_length, 8),
            "leg_scale_ratio": round(leg_ratio, 8),
            "declared_frame": {
                key: [round(float(v), 8) for v in value]
                for key, value in target_frame.items()
            },
        },
        "retarget": {
            "frame_count": source["frame_count"],
            "forward_root_translation_removed": True,
            "vertical_root_translation_preserved": True,
            "lateral_root_translation_preserved": True,
            "mapping": mapping,
            "spine_distribution": spine_weights,
        },
    }
    return armature, action, report


def look_at(obj: bpy.types.Object, target: Vector) -> None:
    direction = target - obj.location
    require(direction.length > 1e-8, "Camera look-at direction is zero.")
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def choose_preview_engine(scene: bpy.types.Scene) -> str:
    engine_property = scene.render.bl_rna.properties["engine"]
    available = {item.identifier for item in engine_property.enum_items}
    for candidate in (
        "BLENDER_EEVEE_NEXT",
        "BLENDER_EEVEE",
        "BLENDER_WORKBENCH",
    ):
        if candidate in available:
            scene.render.engine = candidate
            return candidate
    raise RuntimeError(
        f"No supported preview render engine available: {sorted(available)}"
    )


def configure_video_output(scene: bpy.types.Scene) -> str:
    image_settings = scene.render.image_settings
    media_property = image_settings.bl_rna.properties.get("media_type")
    if media_property is not None:
        media_values = {item.identifier for item in media_property.enum_items}
        if "VIDEO" in media_values:
            image_settings.media_type = "VIDEO"
            return "MEDIA_TYPE_VIDEO"

    format_property = image_settings.bl_rna.properties.get("file_format")
    if format_property is not None:
        format_values = {item.identifier for item in format_property.enum_items}
        if "FFMPEG" in format_values:
            image_settings.file_format = "FFMPEG"
            return "FILE_FORMAT_FFMPEG"

    raise RuntimeError(
        "Blender exposes neither media_type=VIDEO nor file_format=FFMPEG."
    )


def configure_image_output(scene: bpy.types.Scene) -> str:
    image_settings = scene.render.image_settings
    media_property = image_settings.bl_rna.properties.get("media_type")
    if media_property is not None:
        media_values = {item.identifier for item in media_property.enum_items}
        if "IMAGE" in media_values:
            image_settings.media_type = "IMAGE"

    format_property = image_settings.bl_rna.properties.get("file_format")
    if format_property is not None:
        format_values = {item.identifier for item in format_property.enum_items}
        if "PNG" in format_values:
            image_settings.file_format = "PNG"
            return "FILE_FORMAT_PNG"

    raise RuntimeError(
        "Blender image output does not expose PNG in the current media mode."
    )




def make_preview_material(
    name: str,
    base_color: tuple[float, float, float, float],
) -> bpy.types.Material:
    material = bpy.data.materials.new(name)
    material.use_nodes = True
    nodes = material.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    if bsdf is None:
        raise RuntimeError("Preview Principled BSDF node missing.")
    bsdf.inputs["Base Color"].default_value = base_color
    bsdf.inputs["Roughness"].default_value = 0.58
    if "Metallic" in bsdf.inputs:
        bsdf.inputs["Metallic"].default_value = 0.0
    return material


def assign_preview_material(
    material: bpy.types.Material,
) -> None:
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        obj.data.materials.clear()
        obj.data.materials.append(material)


def add_area_light(
    name: str,
    location: Vector,
    energy: float,
    size: float,
    target: Vector,
) -> bpy.types.Object:
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    light = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(light)
    light.location = location
    look_at(light, target)
    return light


def rendered_image_luminance(image_path: Path) -> dict:
    require(image_path.exists(), f"Proof image missing: {image_path}")

    # Blender 5.2 headless can successfully write the proof PNG while leaving
    # Render Result.pixels empty. Reload the actual saved artifact and validate
    # those pixels instead of depending on the transient render buffer.
    image = bpy.data.images.load(
        filepath=str(image_path),
        check_existing=False,
    )
    try:
        image.update()
        pixels = list(image.pixels)
        require(
            len(pixels) >= 4,
            f"Saved proof image contains no pixels: {image_path}",
        )

        total = 0.0
        maximum = 0.0
        alpha_hits = 0
        count = 0
        # Sample every 64th pixel; proof is only a visibility/framing guard.
        step = 4 * 64
        for index in range(0, len(pixels) - 3, step):
            r = float(pixels[index])
            g = float(pixels[index + 1])
            b = float(pixels[index + 2])
            a = float(pixels[index + 3])
            luminance = 0.2126 * r + 0.7152 * g + 0.0722 * b
            total += luminance
            maximum = max(maximum, luminance)
            if a > 0.05:
                alpha_hits += 1
            count += 1

        average = total / max(count, 1)
        alpha_coverage = alpha_hits / max(count, 1)
        return {
            "average": average,
            "maximum": maximum,
            "alpha_coverage": alpha_coverage,
            "sample_count": count,
        }
    finally:
        bpy.data.images.remove(image)


def configure_preview(
    armature: bpy.types.Object,
    target_frame: dict[str, Vector],
    preview_path: Path,
) -> tuple[str, str, Path]:
    scene = bpy.context.scene
    scene.render.resolution_x = 960
    scene.render.resolution_y = 720
    scene.render.resolution_percentage = 100
    scene.render.film_transparent = False

    engine = choose_preview_engine(scene)
    video_api = ""

    # Explicit render world: do not depend on Workbench viewport state or
    # imported material viewport colors.
    if scene.world is None:
        scene.world = bpy.data.worlds.new("Phase11_3_PreviewWorld")
    scene.world.use_nodes = True
    background = scene.world.node_tree.nodes.get("Background")
    require(background is not None, "Preview world Background node missing.")
    background.inputs["Color"].default_value = (0.92, 0.93, 0.95, 1.0)
    background.inputs["Strength"].default_value = 0.8

    preview_material = make_preview_material(
        "Phase11_3_CharacterPreview",
        (0.34, 0.44, 0.68, 1.0),
    )
    assign_preview_material(preview_material)

    world_basis = armature.matrix_world.to_3x3()
    side_world = unit(world_basis @ target_frame["left"], "preview side")
    up_world = unit(world_basis @ target_frame["up"], "preview up")
    front_world = unit(world_basis @ target_frame["front"], "preview front")

    scene.frame_set(scene.frame_start)
    bpy.context.view_layer.update()

    def bone_world(name: str) -> Vector:
        return armature.matrix_world @ armature.pose.bones[name].matrix.translation

    tracked = [
        "Hips", "Head",
        "Hand_L", "Hand_R",
        "Foot_L", "Foot_R",
        "Lower_Leg_L", "Lower_Leg_R",
    ]
    points: list[Vector] = []
    for frame_number in range(scene.frame_start, scene.frame_end + 1):
        scene.frame_set(frame_number)
        bpy.context.view_layer.update()
        points.extend(bone_world(name) for name in tracked)

    require(points, "Preview framing has no tracked world-space points.")

    center = sum(points, Vector((0.0, 0.0, 0.0))) / len(points)
    up_values = [point.dot(up_world) for point in points]
    side_values = [point.dot(front_world) for point in points]
    vertical_extent = max(up_values) - min(up_values)
    horizontal_extent = max(side_values) - min(side_values)
    radius = max(max((point - center).length for point in points), 1.0)

    camera_data = bpy.data.cameras.new("Phase11_3_PreviewCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(
        vertical_extent * 1.45,
        horizontal_extent * 1.15,
        radius * 1.65,
        2.0,
    )
    camera_data.clip_start = 0.01
    camera_data.clip_end = max(radius * 12.0, 100.0)

    camera = bpy.data.objects.new("Phase11_3_PreviewCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = center + side_world * max(radius * 4.0, 5.0)
    look_at(camera, center)
    scene.camera = camera

    scene.frame_set(scene.frame_start)
    bpy.context.view_layer.update()

    foot_world_z = min(bone_world("Foot_L").z, bone_world("Foot_R").z)
    bpy.ops.mesh.primitive_plane_add(
        size=max(radius * 7.0, 8.0),
        location=(center.x, center.y, foot_world_z - 0.035),
    )
    floor = bpy.context.active_object
    floor.name = "Phase11_3_PreviewFloor"
    floor_material = make_preview_material(
        "Phase11_3_FloorPreview",
        (0.72, 0.74, 0.78, 1.0),
    )
    floor.data.materials.append(floor_material)

    add_area_light(
        "Phase11_3_Key",
        center + side_world * (radius * 2.2) + up_world * (radius * 2.4)
        + front_world * (radius * 1.2),
        1100.0,
        max(radius * 2.0, 3.0),
        center,
    )
    add_area_light(
        "Phase11_3_Fill",
        center - side_world * (radius * 1.3) + up_world * (radius * 1.2)
        - front_world * (radius * 1.5),
        650.0,
        max(radius * 2.5, 4.0),
        center,
    )

    proof_path = preview_path.with_name(
        preview_path.stem + "_proof.png"
    )
    # Proof must establish that the animated character itself is in frame.
    # A bright world background or floor must not be enough to pass.
    floor.hide_render = True
    scene.render.film_transparent = True
    scene.render.filepath = str(proof_path)
    configure_image_output(scene)
    scene.frame_set(scene.frame_start)
    bpy.ops.render.render(write_still=True)

    luminance = rendered_image_luminance(proof_path)
    require(
        luminance["alpha_coverage"] > 0.002
        and luminance["maximum"] > 0.08,
        "Preview proof does not contain a visible character: "
        f"{luminance}",
    )

    # Restore normal video presentation only after the character proof passes.
    floor.hide_render = False
    scene.render.film_transparent = False
    video_api = configure_video_output(scene)
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = str(preview_path)

    scene["phase11_3_preview_proof_average_luminance"] = luminance["average"]
    scene["phase11_3_preview_proof_max_luminance"] = luminance["maximum"]
    scene["phase11_3_preview_proof_alpha_coverage"] = luminance["alpha_coverage"]

    return engine, video_api, proof_path


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    source_path = Path(args.source_blend).resolve()
    contract_path = Path(args.contract).resolve()
    output_blend = Path(args.output_blend).resolve()
    preview_path = Path(args.preview).resolve()
    report_path = Path(args.report).resolve()

    require(source_path.exists(), f"Source blend missing: {source_path}")
    require(contract_path.exists(), f"Retarget contract missing: {contract_path}")
    contract = json.loads(contract_path.read_text(encoding="utf-8"))

    source_sha = sha256_file(source_path)
    target_path = repo / contract["target"]["glb"]
    target_sha = sha256_file(target_path)

    source = sample_source(source_path, contract)
    armature, action, report = retarget_to_low_poly(repo, contract, source)

    target_seed = json.loads(
        (repo / contract["target"]["calibration_seed"]).read_text(encoding="utf-8")
    )
    target_frame = declared_target_frame(target_seed)

    output_blend.parent.mkdir(parents=True, exist_ok=True)
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    engine, video_api, proof_path = configure_preview(
        armature,
        target_frame,
        preview_path,
    )

    report["source"]["path"] = str(source_path)
    report["source"]["sha256"] = source_sha
    report["target"]["sha256"] = target_sha
    report["preview"] = {
        "engine": engine,
        "video_output_api": video_api,
        "path": str(preview_path),
        "proof_path": str(proof_path),
        "proof_average_luminance": round(
            float(bpy.context.scene[
                "phase11_3_preview_proof_average_luminance"
            ]),
            8,
        ),
        "proof_max_luminance": round(
            float(bpy.context.scene[
                "phase11_3_preview_proof_max_luminance"
            ]),
            8,
        ),
        "proof_alpha_coverage": round(
            float(bpy.context.scene[
                "phase11_3_preview_proof_alpha_coverage"
            ]),
            8,
        ),
        "rendered": not args.skip_render,
    }

    bpy.ops.wm.save_as_mainfile(filepath=str(output_blend))

    if not args.skip_render:
        bpy.context.scene.frame_set(bpy.context.scene.frame_start)
        bpy.ops.render.render(animation=True)

    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("PHASE11_3_AUTHORED_STUMBLE_RETARGET=PASS")
    print(f"SOURCE_ACTION={source['action_name']}")
    print(
        f"FRAMES={source['frame_start']}..{source['frame_end']} "
        f"COUNT={source['frame_count']}"
    )
    print(f"FPS={source['fps']:.6f}")
    print(
        "MARKERS="
        + " | ".join(
            f"{label}@{frame}"
            for label, frame in source["timeline_markers"].items()
        )
    )
    print(f"TARGET_ACTION={action.name}")
    print(f"OUTPUT_BLEND={output_blend}")
    print(f"PREVIEW={preview_path}")
    print(f"REPORT={report_path}")


if __name__ == "__main__":
    main()
