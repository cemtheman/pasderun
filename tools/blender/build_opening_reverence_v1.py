#!/usr/bin/env python3
"""Phase 10.4.3 — Blender-native IK authored opening reverence.

The source GLB is immutable. This authoring pass creates temporary IK targets
and pole controls, lets Blender solve the imported rig with its native IK,
visually bakes the evaluated pose to Opening_Reverence_v1, removes every
temporary constraint/control, exports a clean GLB, and renders an MP4 preview.

Runtime Godot code is intentionally out of scope until the preview passes
visual ballet QA.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector


ACTION_NAME = "Opening_Reverence_v1"
PHASE = "10.4.5"
FPS = 30
START_FRAME = 0
END_FRAME = 120

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
    {
        "frame": 0, "name": "READY_LOW",
        "arm_shape": "BRAS_BAS", "plie": 0.00, "cross": 0.00,
        "turnout_deg": 24.0,
        "torso_deg": 0.0, "chest_deg": 0.0, "head_deg": 0.0,
        "clavicle_deg": 0.0,
    },
    {
        "frame": 14, "name": "BRAS_BAS",
        "arm_shape": "BRAS_BAS", "plie": 0.00, "cross": 0.04,
        "turnout_deg": 24.0,
        "torso_deg": 0.0, "chest_deg": 0.0, "head_deg": 0.0,
        "clavicle_deg": 0.0,
    },
    {
        "frame": 34, "name": "EN_AVANT_PASSAGE",
        "arm_shape": "EN_AVANT", "plie": 0.05, "cross": 0.24,
        "turnout_deg": 26.0,
        "torso_deg": 0.0, "chest_deg": 0.0, "head_deg": 0.0,
        "clavicle_deg": 0.8,
    },
    {
        "frame": 56, "name": "PLACEMENT_AND_SOFTEN",
        "arm_shape": "OPEN_HALF", "plie": 0.40, "cross": 0.78,
        "turnout_deg": 30.0,
        "torso_deg": 3.0, "chest_deg": 1.0, "head_deg": 0.5,
        "clavicle_deg": 1.0,
    },
    {
        "frame": 72, "name": "ACKNOWLEDGEMENT",
        "arm_shape": "ACK_LOW_OPEN", "plie": 0.86, "cross": 1.00,
        "turnout_deg": 32.0,
        "torso_deg": 11.0, "chest_deg": 4.0, "head_deg": 6.0,
        "clavicle_deg": 1.2,
    },
    {
        "frame": 94, "name": "RISE_AND_OPEN",
        "arm_shape": "OPEN", "plie": 0.18, "cross": 1.00,
        "turnout_deg": 30.0,
        "torso_deg": 1.5, "chest_deg": 0.5, "head_deg": 1.0,
        "clavicle_deg": 1.0,
    },
    {
        "frame": 108, "name": "LOWERING_SECOND",
        "arm_shape": "LOWERING_SECOND", "plie": 0.04, "cross": 0.55,
        "turnout_deg": 27.0,
        "torso_deg": 0.0, "chest_deg": 0.0, "head_deg": 0.0,
        "clavicle_deg": 0.4,
    },
    {
        "frame": 120, "name": "READY_RESOLUTION",
        "arm_shape": "RESOLVE", "plie": 0.00, "cross": 0.00,
        "turnout_deg": 24.0,
        "torso_deg": 0.0, "chest_deg": 0.0, "head_deg": 0.0,
        "clavicle_deg": 0.0,
    },
]

# Classical silhouette targets. Coordinates are expressed as fractions of one
# shoulder-to-wrist reach in the inferred dancer basis.
# Elbow and wrist are authored as explicit ballet landmarks. This removes
# the indirect hand-target + pole approximation that produced chicken-wing
# silhouettes in V3/V4. Only en avant carries substantial forward depth.
ARM_SHAPES = {
    "BRAS_BAS": {
        "wrist_side": 0.12, "wrist_forward": 0.06, "wrist_down": 0.72,
        "elbow_side": 0.38, "elbow_forward": 0.05, "elbow_down": 0.42,
    },
    "EN_AVANT": {
        "wrist_side": 0.06, "wrist_forward": 0.35, "wrist_down": 0.30,
        "elbow_side": 0.36, "elbow_forward": 0.22, "elbow_down": 0.20,
    },
    "OPEN_HALF": {
        "wrist_side": 0.42, "wrist_forward": 0.08, "wrist_down": 0.22,
        "elbow_side": 0.36, "elbow_forward": 0.06, "elbow_down": 0.12,
    },
    "ACK_LOW_OPEN": {
        "wrist_side": 0.58, "wrist_forward": 0.04, "wrist_down": 0.42,
        "elbow_side": 0.40, "elbow_forward": 0.04, "elbow_down": 0.24,
    },
    "OPEN": {
        "wrist_side": 0.66, "wrist_forward": 0.04, "wrist_down": 0.14,
        "elbow_side": 0.38, "elbow_forward": 0.04, "elbow_down": 0.08,
    },
    "LOWERING_SECOND": {
        "wrist_side": 0.46, "wrist_forward": 0.05, "wrist_down": 0.42,
        "elbow_side": 0.36, "elbow_forward": 0.04, "elbow_down": 0.22,
    },
    "RESOLVE": {
        "wrist_side": 0.12, "wrist_forward": 0.06, "wrist_down": 0.72,
        "elbow_side": 0.38, "elbow_forward": 0.05, "elbow_down": 0.42,
    },
}


def parse_args() -> argparse.Namespace:
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--blend-output")
    parser.add_argument("--preview")
    return parser.parse_args(argv)


def vec3(value: Vector) -> list[float]:
    return [round(float(value[0]), 6), round(float(value[1]), 6), round(float(value[2]), 6)]


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
    bpy.context.view_layer.update()


def pose_head(armature: bpy.types.Object, bone_name: str) -> Vector:
    return armature.pose.bones[bone_name].head.copy()


def pose_tail(armature: bpy.types.Object, bone_name: str) -> Vector:
    return armature.pose.bones[bone_name].tail.copy()


def child_vector(armature: bpy.types.Object, parent_name: str, child_name: str) -> Vector:
    return pose_head(armature, child_name) - pose_head(armature, parent_name)


def rest_snapshot(armature: bpy.types.Object) -> dict[str, Vector]:
    return {name: pose_head(armature, name) for name in REQUIRED_BONES}


def joint_length(rest: dict[str, Vector], a: str, b: str) -> float:
    return (rest[b] - rest[a]).length


def canonical_axes(armature: bpy.types.Object) -> dict[str, Vector]:
    hips = pose_head(armature, "Hips")
    head = pose_head(armature, "Head")
    left_shoulder = pose_head(armature, "Upper_Arm_L")
    right_shoulder = pose_head(armature, "Upper_Arm_R")

    up = (head - hips).normalized()
    side_seed = left_shoulder - right_shoulder
    side_seed -= up * side_seed.dot(up)
    side_seed.normalize()

    toe_flow = (
        child_vector(armature, "Foot_L", "Toes_L")
        + child_vector(armature, "Foot_R", "Toes_R")
    ) * 0.5
    toe_flow -= up * toe_flow.dot(up)
    toe_flow -= side_seed * toe_flow.dot(side_seed)
    if toe_flow.length <= 0.000001:
        toe_flow = side_seed.cross(up)
    toe_flow.normalize()

    side = up.cross(toe_flow).normalized()
    if side.dot(side_seed) < 0.0:
        side = -side
    forward = side.cross(up).normalized()
    if forward.dot(toe_flow) < 0.0:
        forward = -forward
    return {"side": side, "up": up, "forward": forward}


def rotate_pose_bone_world(pb: bpy.types.PoseBone, axis: Vector, angle_deg: float) -> None:
    if abs(angle_deg) <= 0.00001:
        return
    rotation = Quaternion(axis.normalized(), math.radians(angle_deg))
    matrix = pb.matrix.copy()
    rotated = rotation.to_matrix() @ matrix.to_3x3()
    result = rotated.to_4x4()
    result.translation = matrix.translation
    pb.matrix = result


def translate_pose_bone_world(pb: bpy.types.PoseBone, offset: Vector) -> None:
    matrix = pb.matrix.copy()
    matrix.translation += offset
    pb.matrix = matrix


def local_to_world(armature: bpy.types.Object, point: Vector) -> Vector:
    return armature.matrix_world @ point


def create_control(name: str) -> bpy.types.Object:
    control = bpy.data.objects.new(name, None)
    control.empty_display_type = "SPHERE"
    control.empty_display_size = 0.045
    bpy.context.scene.collection.objects.link(control)
    return control


def set_control_location(
    control: bpy.types.Object,
    armature: bpy.types.Object,
    local_point: Vector,
    frame: int | None = None,
) -> None:
    control.location = local_to_world(armature, local_point)
    if frame is not None:
        control.keyframe_insert(data_path="location", frame=frame)


def set_control_rotation_world(
    control: bpy.types.Object,
    rotation: Quaternion,
    frame: int | None = None,
) -> None:
    control.rotation_mode = "QUATERNION"
    control.rotation_quaternion = rotation
    if frame is not None:
        control.keyframe_insert(data_path="rotation_quaternion", frame=frame)


def create_ik_constraint(
    armature: bpy.types.Object,
    lower_bone: str,
    target: bpy.types.Object,
    pole: bpy.types.Object,
) -> bpy.types.Constraint:
    pb = armature.pose.bones[lower_bone]
    constraint = pb.constraints.new("IK")
    constraint.name = f"Phase1043_IK_{lower_bone}"
    constraint.target = target
    constraint.pole_target = pole
    constraint.chain_count = 2
    constraint.use_tail = True
    constraint.use_stretch = False
    constraint.iterations = 128
    return constraint


def choose_roll_axis(
    armature: bpy.types.Object,
    bone_name: str,
    reference_normal: Vector,
) -> tuple[str, float]:
    """Choose the rest transverse axis that best represents arm-plane roll."""
    basis = armature.data.bones[bone_name].matrix_local.to_3x3()
    candidates = {
        "X": basis.col[0].normalized(),
        "Z": basis.col[2].normalized(),
    }
    axis_name = max(
        candidates,
        key=lambda name: abs(candidates[name].dot(reference_normal)),
    )
    alignment = candidates[axis_name].dot(reference_normal)
    return axis_name, 1.0 if alignment >= 0.0 else -1.0


def set_roll_stable_bone_frame(
    armature: bpy.types.Object,
    bone_name: str,
    target_head: Vector,
    plane_normal: Vector,
    reference_normal: Vector,
) -> None:
    """Aim bone Y at target while explicitly preserving ballet-plane roll."""
    pb = armature.pose.bones[bone_name]
    direction = target_head - pb.head
    if direction.length <= 0.000001:
        return
    y_axis = direction.normalized()

    normal = plane_normal - y_axis * plane_normal.dot(y_axis)
    if normal.length <= 0.000001:
        normal = (
            reference_normal
            - y_axis * reference_normal.dot(y_axis)
        )
    if normal.length <= 0.000001:
        raise RuntimeError(
            f"Cannot construct roll-stable frame for {bone_name}."
        )
    normal.normalize()
    if normal.dot(reference_normal) < 0.0:
        normal = -normal

    roll_axis, roll_sign = choose_roll_axis(
        armature,
        bone_name,
        reference_normal,
    )
    transverse = normal * roll_sign

    if roll_axis == "Z":
        z_axis = transverse
        x_axis = y_axis.cross(z_axis).normalized()
        z_axis = x_axis.cross(y_axis).normalized()
    else:
        x_axis = transverse
        z_axis = x_axis.cross(y_axis).normalized()
        x_axis = y_axis.cross(z_axis).normalized()

    basis = Matrix((x_axis, y_axis, z_axis)).transposed()
    matrix = basis.to_4x4()
    matrix.translation = pb.head.copy()
    pb.matrix = matrix
    bpy.context.view_layer.update()


def create_world_rotation_constraint(
    armature: bpy.types.Object,
    bone_name: str,
    target: bpy.types.Object,
) -> bpy.types.Constraint:
    pb = armature.pose.bones[bone_name]
    constraint = pb.constraints.new("COPY_ROTATION")
    constraint.name = f"Phase1043_FootRotation_{bone_name}"
    constraint.target = target
    constraint.target_space = "WORLD"
    constraint.owner_space = "WORLD"
    constraint.mix_mode = "REPLACE"
    return constraint


def projected_direction(vector: Vector, axis: Vector) -> Vector:
    projected = vector - axis * vector.dot(axis)
    if projected.length <= 0.000001:
        return Vector((0.0, 0.0, 0.0))
    return projected.normalized()


def pole_alignment_score(
    armature: bpy.types.Object,
    root_bone: str,
    joint_bone: str,
    target: bpy.types.Object,
    pole: bpy.types.Object,
) -> float:
    root = pose_head(armature, root_bone)
    joint = pose_head(armature, joint_bone)
    target_local = armature.matrix_world.inverted() @ target.matrix_world.translation
    pole_local = armature.matrix_world.inverted() @ pole.matrix_world.translation
    axis = target_local - root
    if axis.length <= 0.000001:
        return -1.0
    axis.normalize()
    actual = projected_direction(joint - root, axis)
    desired = projected_direction(pole_local - root, axis)
    if actual.length <= 0.000001 or desired.length <= 0.000001:
        return -1.0
    return actual.dot(desired)


def calibrate_pole_angle(
    armature: bpy.types.Object,
    constraint: bpy.types.Constraint,
    root_bone: str,
    joint_bone: str,
    target: bpy.types.Object,
    pole: bpy.types.Object,
) -> float:
    """Find the rig-specific pole angle instead of assuming bone roll."""
    best_angle = 0.0
    best_score = -2.0

    for step in range(72):
        angle = -math.pi + (2.0 * math.pi * step / 72.0)
        constraint.pole_angle = angle
        bpy.context.view_layer.update()
        score = pole_alignment_score(
            armature, root_bone, joint_bone, target, pole
        )
        if score > best_score:
            best_score = score
            best_angle = angle

    for degree_offset in range(-8, 9):
        angle = best_angle + math.radians(degree_offset)
        constraint.pole_angle = angle
        bpy.context.view_layer.update()
        score = pole_alignment_score(
            armature, root_bone, joint_bone, target, pole
        )
        if score > best_score:
            best_score = score
            best_angle = angle

    constraint.pole_angle = best_angle
    bpy.context.view_layer.update()
    return best_angle


def apply_body_landmark(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
    pose: dict,
) -> None:
    side = axes["side"]
    up = axes["up"]
    forward = axes["forward"]

    total_leg = (
        joint_length(rest, "Upper_Leg_L", "Lower_Leg_L")
        + joint_length(rest, "Lower_Leg_L", "Foot_L")
    )
    hip_width = joint_length(rest, "Upper_Leg_L", "Upper_Leg_R")
    plie = float(pose["plie"])
    cross = float(pose["cross"])

    support_shift = side * hip_width * 0.085 * cross
    # A classical révérence needs a visible vertical descent. The previous
    # 8.2% factor read almost upright in the static evidence sheet.
    pelvis_drop = -up * total_leg * 0.145 * plie
    translate_pose_bone_world(
        armature.pose.bones["Hips"],
        support_shift + pelvis_drop,
    )
    bpy.context.view_layer.update()

    rotate_pose_bone_world(
        armature.pose.bones["Spine 1"],
        side,
        float(pose["torso_deg"]),
    )
    bpy.context.view_layer.update()
    rotate_pose_bone_world(
        armature.pose.bones["Chest"],
        side,
        float(pose["chest_deg"]),
    )
    bpy.context.view_layer.update()
    rotate_pose_bone_world(
        armature.pose.bones["Head"],
        side,
        float(pose["head_deg"]),
    )
    bpy.context.view_layer.update()

    clavicle_deg = float(pose["clavicle_deg"])
    rotate_pose_bone_world(
        armature.pose.bones["Clavicle_L"],
        forward,
        clavicle_deg,
    )
    bpy.context.view_layer.update()
    rotate_pose_bone_world(
        armature.pose.bones["Clavicle_R"],
        forward,
        -clavicle_deg,
    )
    bpy.context.view_layer.update()

    if plie > 0.0:
        translate_pose_bone_world(
            armature.pose.bones["Chest"],
            forward * total_leg * 0.0045 * plie,
        )
        bpy.context.view_layer.update()


def key_body_landmark(armature: bpy.types.Object, frame: int) -> None:
    for bone_name in (
        "Hips", "Spine", "Spine 1", "Chest", "Neck", "Head",
        "Clavicle_L", "Clavicle_R",
    ):
        pb = armature.pose.bones[bone_name]
        pb.rotation_mode = "QUATERNION"
        pb.keyframe_insert(
            data_path="rotation_quaternion", frame=frame, group=bone_name
        )
        pb.keyframe_insert(
            data_path="location", frame=frame, group=bone_name
        )


def arm_control_points(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
    pose: dict,
    left: bool,
) -> tuple[Vector, Vector, Vector]:
    """Return explicit elbow, wrist and hand-finish ballet landmarks."""
    side = axes["side"]
    up = axes["up"]
    forward = axes["forward"]
    suffix = "L" if left else "R"
    side_sign = 1.0 if left else -1.0
    shape = ARM_SHAPES[str(pose["arm_shape"])]

    shoulder_center = (
        pose_head(armature, "Upper_Arm_L")
        + pose_head(armature, "Upper_Arm_R")
    ) * 0.5
    upper_length = joint_length(
        rest, f"Upper_Arm_{suffix}", f"Lower_Arm_{suffix}"
    )
    lower_length = joint_length(
        rest, f"Lower_Arm_{suffix}", f"Hand_{suffix}"
    )
    hand_length = joint_length(
        rest, f"Hand_{suffix}", f"Middle_{suffix}"
    )
    reach = upper_length + lower_length

    elbow_target = (
        shoulder_center
        + side * side_sign * reach * float(shape["elbow_side"])
        + forward * reach * float(shape["elbow_forward"])
        - up * reach * float(shape["elbow_down"])
    )
    wrist_target = (
        shoulder_center
        + side * side_sign * reach * float(shape["wrist_side"])
        + forward * reach * float(shape["wrist_forward"])
        - up * reach * float(shape["wrist_down"])
    )

    forearm_tangent = (wrist_target - elbow_target).normalized()
    inward = -side * side_sign
    hand_direction = (
        forearm_tangent * 0.96
        + inward * 0.10
        - up * 0.04
    ).normalized()
    finish_target = (
        wrist_target
        + hand_direction * max(hand_length * 1.5, reach * 0.08)
    )
    return elbow_target, wrist_target, finish_target


def apply_arm_landmark_pose(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
    pose: dict,
) -> None:
    """Author upper arm, forearm and hand with explicit position + roll."""
    forward = axes["forward"]

    for left in (True, False):
        suffix = "L" if left else "R"
        side_sign = 1.0 if left else -1.0
        reference_normal = (forward * side_sign).normalized()

        elbow_target, wrist_target, finish_target = arm_control_points(
            armature,
            axes,
            rest,
            pose,
            left,
        )

        shoulder = pose_head(armature, f"Upper_Arm_{suffix}")
        upper_direction = elbow_target - shoulder
        forearm_direction = wrist_target - elbow_target
        plane_normal = upper_direction.cross(forearm_direction)
        if plane_normal.length <= 0.000001:
            plane_normal = reference_normal.copy()
        else:
            plane_normal.normalize()
            if plane_normal.dot(reference_normal) < 0.0:
                plane_normal = -plane_normal

        set_roll_stable_bone_frame(
            armature,
            f"Upper_Arm_{suffix}",
            elbow_target,
            plane_normal,
            reference_normal,
        )
        set_roll_stable_bone_frame(
            armature,
            f"Lower_Arm_{suffix}",
            wrist_target,
            plane_normal,
            reference_normal,
        )
        set_roll_stable_bone_frame(
            armature,
            f"Hand_{suffix}",
            finish_target,
            plane_normal,
            reference_normal,
        )


def key_arm_landmark_pose(
    armature: bpy.types.Object,
    frame: int,
) -> None:
    for suffix in ("L", "R"):
        for bone_name in (
            f"Upper_Arm_{suffix}",
            f"Lower_Arm_{suffix}",
            f"Hand_{suffix}",
        ):
            pb = armature.pose.bones[bone_name]
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


def leg_control_points(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
    pose: dict,
    left: bool,
) -> tuple[Vector, Vector]:
    side = axes["side"]
    up = axes["up"]
    forward = axes["forward"]
    side_sign = 1.0 if left else -1.0
    suffix = "L" if left else "R"
    cross = float(pose["cross"])

    hip_width = joint_length(rest, "Upper_Leg_L", "Upper_Leg_R")
    total_leg = (
        joint_length(rest, f"Upper_Leg_{suffix}", f"Lower_Leg_{suffix}")
        + joint_length(rest, f"Lower_Leg_{suffix}", f"Foot_{suffix}")
    )

    ankle = rest[f"Foot_{suffix}"].copy()
    if not left:
        ankle += side * hip_width * 1.75 * cross
        ankle -= forward * total_leg * 0.065 * cross

    hip = pose_head(armature, f"Upper_Leg_{suffix}")
    pole_direction = (
        forward * 0.72
        + side * side_sign * 0.42
        - up * 0.10
    ).normalized()
    pole = hip + pole_direction * total_leg * 1.25
    return ankle, pole


def key_leg_controls(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
    pose: dict,
    controls: dict[str, bpy.types.Object],
    foot_world_rotations: dict[str, Quaternion],
) -> None:
    frame = int(pose["frame"])
    for left in (True, False):
        suffix = "L" if left else "R"
        side_sign = 1.0 if left else -1.0

        ankle_target, leg_pole = leg_control_points(
            armature,
            axes,
            rest,
            pose,
            left,
        )
        set_control_location(
            controls[f"leg_target_{suffix}"],
            armature,
            ankle_target,
            frame,
        )
        set_control_location(
            controls[f"leg_pole_{suffix}"],
            armature,
            leg_pole,
            frame,
        )

        world_up = (
            armature.matrix_world.to_3x3() @ axes["up"]
        ).normalized()
        turnout = Quaternion(
            world_up,
            math.radians(side_sign * float(pose["turnout_deg"])),
        )
        set_control_rotation_world(
            controls[f"foot_rotation_{suffix}"],
            turnout @ foot_world_rotations[suffix],
            frame,
        )


def configure_object_interpolation(objects: list[bpy.types.Object]) -> None:
    for obj in objects:
        if obj.animation_data is None or obj.animation_data.action is None:
            continue
        action = obj.animation_data.action
        fcurves = getattr(action, "fcurves", None)
        if fcurves is None:
            continue
        for curve in fcurves:
            for point in curve.keyframe_points:
                point.interpolation = "BEZIER"
                point.handle_left_type = "AUTO_CLAMPED"
                point.handle_right_type = "AUTO_CLAMPED"


def select_armature_bones_for_bake(armature: bpy.types.Object) -> None:
    # Blender 5.2 removed direct Bone.select mutation. Select the armature's
    # pose bones through the pose operator instead; this keeps the bake path
    # compatible without changing the authored motion or IK solution.
    bpy.ops.object.select_all(action="DESELECT")
    bpy.context.view_layer.objects.active = armature
    armature.select_set(True)
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")


def bake_authoring_constraints(armature: bpy.types.Object) -> None:
    select_armature_bones_for_bake(armature)
    props = bpy.ops.nla.bake.get_rna_type().properties.keys()
    kwargs = {
        "frame_start": START_FRAME,
        "frame_end": END_FRAME,
        "step": 1,
        "only_selected": True,
        "visual_keying": True,
        "clear_constraints": True,
        "use_current_action": True,
        "clean_curves": False,
        "bake_types": {"POSE"},
    }
    filtered = {key: value for key, value in kwargs.items() if key in props}
    result = bpy.ops.nla.bake(**filtered)
    if "FINISHED" not in result:
        raise RuntimeError(f"Authoring constraint bake did not finish: {result}")
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()


def remove_controls(controls: dict[str, bpy.types.Object]) -> None:
    for control in list(controls.values()):
        if control.name in bpy.data.objects:
            bpy.data.objects.remove(control, do_unlink=True)


def constraint_count(armature: bpy.types.Object) -> int:
    return sum(len(pb.constraints) for pb in armature.pose.bones)


def temporary_controls_remaining() -> list[str]:
    return sorted(
        obj.name for obj in bpy.data.objects
        if obj.name.startswith(("P1043_", "P1044_", "P1045_"))
    )


def configure_action_interpolation(action: bpy.types.Action) -> None:
    # Native IK has already been evaluated and visually sampled every frame.
    # LINEAR playback preserves those baked samples instead of re-curving them.
    fcurves = getattr(action, "fcurves", None)
    if fcurves is None:
        return
    for curve in fcurves:
        for point in curve.keyframe_points:
            point.interpolation = "LINEAR"


def export_glb(output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    props = bpy.ops.export_scene.gltf.get_rna_type().properties.keys()
    kwargs = {
        "filepath": str(output_path),
        "export_format": "GLB",
        "export_animations": True,
    }
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


def look_at(obj: bpy.types.Object, point: Vector) -> None:
    direction = point - obj.location
    obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()


def add_area_light(
    name: str,
    location: Vector,
    target: Vector,
    energy: float,
    size: float,
) -> None:
    data = bpy.data.lights.new(name=name, type="AREA")
    data.energy = energy
    data.shape = "DISK"
    data.size = size
    obj = bpy.data.objects.new(name, data)
    bpy.context.scene.collection.objects.link(obj)
    obj.location = location
    look_at(obj, target)


def choose_preview_engine(scene: bpy.types.Scene) -> str:
    # Blender has used both BLENDER_EEVEE and BLENDER_EEVEE_NEXT identifiers
    # across releases/builds. Probe the runtime enum instead of assuming one.
    engine_property = scene.render.bl_rna.properties["engine"]
    available = {item.identifier for item in engine_property.enum_items}
    for candidate in ("BLENDER_WORKBENCH", "BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        if candidate in available:
            scene.render.engine = candidate
            return candidate
    raise RuntimeError(
        f"No supported preview render engine available: {sorted(available)}"
    )


def configure_video_output(scene: bpy.types.Scene) -> str:
    """Configure Blender video output across pre-5.x and 5.x APIs."""
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
        "Blender build exposes neither media_type=VIDEO nor file_format=FFMPEG."
    )


def configure_preview_scene(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    preview_path: Path,
) -> tuple[str, str]:
    scene = bpy.context.scene
    scene.frame_start = START_FRAME
    scene.frame_end = END_FRAME
    scene.render.fps = FPS
    scene.render.resolution_x = 540
    scene.render.resolution_y = 540
    scene.render.resolution_percentage = 100
    preview_engine = choose_preview_engine(scene)
    video_output_api = configure_video_output(scene)
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"
    scene.render.filepath = str(preview_path)

    hips = pose_head(armature, "Hips")
    head = pose_head(armature, "Head")
    center_local = (hips + head) * 0.5
    center_world = local_to_world(armature, center_local)
    forward_world = (armature.matrix_world.to_3x3() @ axes["forward"]).normalized()
    side_world = (armature.matrix_world.to_3x3() @ axes["side"]).normalized()
    up_world = (armature.matrix_world.to_3x3() @ axes["up"]).normalized()

    camera_data = bpy.data.cameras.new("P1043_PreviewCamera")
    camera = bpy.data.objects.new("P1043_PreviewCamera", camera_data)
    bpy.context.scene.collection.objects.link(camera)
    camera.location = center_world + forward_world * 3.6 + up_world * 0.08
    camera_data.lens = 52.0
    look_at(camera, center_world)
    scene.camera = camera

    add_area_light(
        "P1043_Key",
        center_world + forward_world * 2.2 + side_world * 1.8 + up_world * 2.4,
        center_world,
        900.0,
        3.0,
    )
    add_area_light(
        "P1043_Fill",
        center_world + forward_world * 1.8 - side_world * 1.6 + up_world * 1.8,
        center_world,
        550.0,
        2.5,
    )
    add_area_light(
        "P1043_Rim",
        center_world - forward_world * 1.5 + up_world * 2.6,
        center_world + up_world * 0.4,
        700.0,
        2.0,
    )

    if scene.world is None:
        scene.world = bpy.data.worlds.new("P1043_PreviewWorld")
    scene.world.color = (0.035, 0.035, 0.035)

    bpy.ops.mesh.primitive_plane_add(
        size=6.0,
        location=(0.0, 0.0, 0.0),
    )
    floor = bpy.context.object
    floor.name = "P1043_PreviewFloor"
    material = bpy.data.materials.new("P1043_PreviewFloorMaterial")
    material.diffuse_color = (0.12, 0.12, 0.12, 1.0)
    floor.data.materials.append(material)
    return preview_engine, video_output_api


def render_preview(preview_path: Path) -> None:
    preview_path.parent.mkdir(parents=True, exist_ok=True)
    result = bpy.ops.render.render(animation=True)
    if "FINISHED" not in result:
        raise RuntimeError(f"Preview render did not finish: {result}")


def bone_axes_report(armature: bpy.types.Object) -> dict:
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
    return axes


def setup_leg_controls_and_constraints(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
) -> tuple[
    dict[str, bpy.types.Object],
    dict[str, float],
    dict[str, Quaternion],
]:
    controls: dict[str, bpy.types.Object] = {}
    leg_ik_constraints: dict[
        str, tuple[bpy.types.Constraint, str, str]
    ] = {}

    foot_world_rotations: dict[str, Quaternion] = {}
    for suffix in ("L", "R"):
        foot_pb = armature.pose.bones[f"Foot_{suffix}"]
        foot_world_matrix = armature.matrix_world @ foot_pb.matrix
        foot_world_rotations[suffix] = foot_world_matrix.to_quaternion()

    for left in (True, False):
        suffix = "L" if left else "R"

        controls[f"leg_target_{suffix}"] = create_control(
            f"P1045_LegTarget_{suffix}"
        )
        controls[f"leg_pole_{suffix}"] = create_control(
            f"P1045_LegPole_{suffix}"
        )
        controls[f"foot_rotation_{suffix}"] = create_control(
            f"P1045_FootRotation_{suffix}"
        )

        set_control_location(
            controls[f"leg_target_{suffix}"],
            armature,
            pose_head(armature, f"Foot_{suffix}"),
        )
        set_control_location(
            controls[f"leg_pole_{suffix}"],
            armature,
            pose_head(armature, f"Lower_Leg_{suffix}"),
        )
        set_control_rotation_world(
            controls[f"foot_rotation_{suffix}"],
            foot_world_rotations[suffix],
        )

        leg_constraint = create_ik_constraint(
            armature,
            f"Lower_Leg_{suffix}",
            controls[f"leg_target_{suffix}"],
            controls[f"leg_pole_{suffix}"],
        )
        leg_constraint.name = f"Phase1045_LegIK_{suffix}"
        leg_ik_constraints[f"leg_{suffix}"] = (
            leg_constraint,
            f"Upper_Leg_{suffix}",
            f"Lower_Leg_{suffix}",
        )
        create_world_rotation_constraint(
            armature,
            f"Foot_{suffix}",
            controls[f"foot_rotation_{suffix}"],
        )
        bpy.context.view_layer.update()

    calibration_pose = POSES[3]
    clear_pose(armature)
    apply_body_landmark(armature, axes, rest, calibration_pose)

    for left in (True, False):
        suffix = "L" if left else "R"
        ankle_target, leg_pole = leg_control_points(
            armature,
            axes,
            rest,
            calibration_pose,
            left,
        )
        set_control_location(
            controls[f"leg_target_{suffix}"],
            armature,
            ankle_target,
        )
        set_control_location(
            controls[f"leg_pole_{suffix}"],
            armature,
            leg_pole,
        )

    bpy.context.view_layer.update()

    pole_angles: dict[str, float] = {}
    for key, (constraint, root_bone, joint_bone) in leg_ik_constraints.items():
        suffix = key[-1]
        angle = calibrate_pole_angle(
            armature,
            constraint,
            root_bone,
            joint_bone,
            controls[f"leg_target_{suffix}"],
            controls[f"leg_pole_{suffix}"],
        )
        pole_angles[key] = round(math.degrees(angle), 4)

    return controls, pole_angles, foot_world_rotations


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    report_path = Path(args.report).resolve()
    blend_output = Path(args.blend_output).resolve() if args.blend_output else None
    preview_path = Path(args.preview).resolve() if args.preview else None

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

    actions_before = [action_summary(action) for action in bpy.data.actions]
    clear_pose(armature)
    axes = canonical_axes(armature)
    rest = rest_snapshot(armature)

    if ACTION_NAME in bpy.data.actions:
        bpy.data.actions.remove(bpy.data.actions[ACTION_NAME])

    action = bpy.data.actions.new(ACTION_NAME)
    action.use_fake_user = True
    armature.animation_data_create()
    armature.animation_data.action = action

    scene = bpy.context.scene
    scene.render.fps = FPS
    scene.frame_start = START_FRAME
    scene.frame_end = END_FRAME

    controls, pole_angles, foot_world_rotations = (
        setup_leg_controls_and_constraints(armature, axes, rest)
    )

    # Author body + semantic controls only at choreography landmarks.
    for pose in POSES:
        frame = int(pose["frame"])
        scene.frame_set(frame)
        clear_pose(armature)
        apply_body_landmark(armature, axes, rest, pose)
        apply_arm_landmark_pose(armature, axes, rest, pose)
        key_body_landmark(armature, frame)
        key_arm_landmark_pose(armature, frame)
        key_leg_controls(
            armature,
            axes,
            rest,
            pose,
            controls,
            foot_world_rotations,
        )

    configure_object_interpolation(list(controls.values()))

    # Sparse roll-stable arm frames interpolate in the action while leg IK
    # evaluates through Blender. Bake the combined visual result frame-by-frame.
    scene.frame_set(START_FRAME)
    bake_authoring_constraints(armature)
    remove_controls(controls)
    configure_action_interpolation(action)
    scene.frame_set(START_FRAME)

    remaining_constraints = constraint_count(armature)
    remaining_controls = temporary_controls_remaining()
    if remaining_constraints != 0:
        raise RuntimeError(
            f"Expected zero constraints after bake, found {remaining_constraints}."
        )
    if remaining_controls:
        raise RuntimeError(
            f"Temporary controls survived bake: {remaining_controls}"
        )

    # Fail fast on Blender video-output API compatibility before paying the
    # cost of GLB export. Full preview scene creation still happens afterward
    # so camera/light/floor helpers never enter the exported asset.
    if preview_path is not None:
        configure_video_output(scene)

    if blend_output is not None:
        blend_output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_output))

    export_glb(output_path)

    preview_engine = None
    video_output_api = None
    if preview_path is not None:
        preview_engine, video_output_api = configure_preview_scene(
            armature, axes, preview_path
        )
        render_preview(preview_path)

    report = {
        "phase": PHASE,
        "authoring_model": (
            "leg native IK + explicit roll-stable arm frames + visual bake"
        ),
        "source_glb": str(input_path),
        "output_glb": str(output_path),
        "blend_output": str(blend_output) if blend_output else None,
        "preview_output": str(preview_path) if preview_path else None,
        "preview_engine": preview_engine,
        "video_output_api": video_output_api,
        "armature": armature.name,
        "fps": FPS,
        "start_frame": START_FRAME,
        "end_frame": END_FRAME,
        "duration_seconds": round((END_FRAME - START_FRAME) / FPS, 4),
        "required_bones_ok": True,
        "actions_before": actions_before,
        "actions_after": [action_summary(a) for a in bpy.data.actions],
        "authored_action": ACTION_NAME,
        "leg_native_ik_baked": True,
        "arm_roll_stable_frames_baked": True,
        "constraints_after_bake": remaining_constraints,
        "temporary_controls_after_bake": remaining_controls,
        "pole_angles_deg": pole_angles,
        "canonical_axes": {
            name: vec3(axis) for name, axis in axes.items()
        },
        "poses": [
            {
                "frame": int(pose["frame"]),
                "name": pose["name"],
                "arm_shape": pose["arm_shape"],
                "plie": pose["plie"],
                "cross": pose["cross"],
                "turnout_deg": pose["turnout_deg"],
            }
            for pose in POSES
        ],
        "bone_axes": bone_axes_report(armature),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("PHASE10_4_5=PASS")
    print(f"ARMATURE={armature.name}")
    print(f"ACTION={ACTION_NAME}")
    print(f"LEG_NATIVE_IK_BAKED={report['leg_native_ik_baked']}")
    print(
        f"ARM_ROLL_STABLE_FRAMES_BAKED={report['arm_roll_stable_frames_baked']}"
    )
    print(f"CONSTRAINTS_AFTER_BAKE={remaining_constraints}")
    print(f"TEMP_CONTROLS_AFTER_BAKE={len(remaining_controls)}")
    print(f"OUTPUT={output_path}")
    print(f"REPORT={report_path}")
    if preview_path is not None:
        print(f"PREVIEW={preview_path}")


if __name__ == "__main__":
    main()
