#!/usr/bin/env python3
"""Phase 10.4.2 — rig-aware authored opening révérence.

The source GLB remains immutable. Poses are authored from semantic joint
targets in armature space. Bone rotations are solved from the imported rig's
actual geometry; no guessed local Euler axis is used.
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

# Reference-derived movement phrase. The frames are choreography landmarks,
# not independent frozen poses; Blender interpolates the continuous phrase.
POSES = [
    {
        "frame": 1, "name": "READY_LOW",
        "arm_shape": "BRAS_BAS", "plie": 0.00, "cross": 0.00,
        "torso_deg": 0.0, "chest_deg": 0.0, "head_deg": 0.0,
    },
    {
        "frame": 9, "name": "BRAS_BAS",
        "arm_shape": "BRAS_BAS", "plie": 0.00, "cross": 0.05,
        "torso_deg": 0.0, "chest_deg": 0.0, "head_deg": 0.0,
    },
    {
        "frame": 20, "name": "EN_AVANT_PASSAGE",
        "arm_shape": "EN_AVANT", "plie": 0.08, "cross": 0.25,
        "torso_deg": 0.0, "chest_deg": 0.0, "head_deg": 0.0,
    },
    {
        "frame": 32, "name": "PLACEMENT_AND_SOFTEN",
        "arm_shape": "OPEN_HALF", "plie": 0.45, "cross": 0.78,
        "torso_deg": 2.0, "chest_deg": 0.5, "head_deg": 0.5,
    },
    {
        "frame": 40, "name": "ACKNOWLEDGEMENT",
        "arm_shape": "OPEN", "plie": 0.78, "cross": 1.00,
        "torso_deg": 5.5, "chest_deg": 2.0, "head_deg": 4.0,
    },
    {
        "frame": 52, "name": "RISE_AND_OPEN",
        "arm_shape": "OPEN", "plie": 0.20, "cross": 1.00,
        "torso_deg": 1.0, "chest_deg": 0.5, "head_deg": 1.0,
    },
    {
        "frame": END_FRAME, "name": "READY_RESOLUTION",
        "arm_shape": "RESOLVE", "plie": 0.00, "cross": 0.00,
        "torso_deg": 0.0, "chest_deg": 0.0, "head_deg": 0.0,
    },
]

# Fractions of one arm's shoulder-to-hand reach. Side is mirrored per arm.
# Forward is inferred from the imported feet/toes rather than hard-coded.
ARM_SHAPES = {
    "BRAS_BAS": {
        "hand_side": 0.12, "hand_forward": 0.30, "hand_down": 0.44,
        "elbow_side": 0.34, "elbow_forward": 0.20, "elbow_down": 0.28,
    },
    "EN_AVANT": {
        "hand_side": 0.05, "hand_forward": 0.46, "hand_down": 0.10,
        "elbow_side": 0.44, "elbow_forward": 0.26, "elbow_down": 0.16,
    },
    "OPEN_HALF": {
        "hand_side": 0.48, "hand_forward": 0.30, "hand_down": 0.10,
        "elbow_side": 0.46, "elbow_forward": 0.28, "elbow_down": 0.12,
    },
    "OPEN": {
        "hand_side": 0.88, "hand_forward": 0.14, "hand_down": 0.08,
        "elbow_side": 0.46, "elbow_forward": 0.30, "elbow_down": 0.10,
    },
    "RESOLVE": {
        "hand_side": 0.14, "hand_forward": 0.25, "hand_down": 0.46,
        "elbow_side": 0.34, "elbow_forward": 0.18, "elbow_down": 0.28,
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


def child_vector(armature: bpy.types.Object, parent_name: str, child_name: str) -> Vector:
    return pose_head(armature, child_name) - pose_head(armature, parent_name)


def translate_pose_bone_world(pb: bpy.types.PoseBone, offset: Vector) -> None:
    matrix = pb.matrix.copy()
    matrix.translation += offset
    pb.matrix = matrix


def rotate_pose_bone_world(pb: bpy.types.PoseBone, axis: Vector, angle_deg: float) -> None:
    if abs(angle_deg) <= 0.00001:
        return
    rotation = Quaternion(axis.normalized(), math.radians(angle_deg))
    matrix = pb.matrix.copy()
    rotated = rotation.to_matrix() @ matrix.to_3x3()
    result = rotated.to_4x4()
    result.translation = matrix.translation
    pb.matrix = result


def aim_parent_to_child(
    armature: bpy.types.Object,
    parent_name: str,
    child_name: str,
    target_child_head: Vector,
) -> float:
    """Swing a parent so its real child-head vector points at a target.

    This works for both connected and offset-child joints, so the unusual
    Upper_Leg -> Lower_Leg spacing in this rig is handled without assuming
    that the parent's edit-bone tail is the anatomical knee.
    """
    parent = armature.pose.bones[parent_name]
    child = armature.pose.bones[child_name]
    current = child.head - parent.head
    desired = target_child_head - parent.head
    if current.length <= 0.000001 or desired.length <= 0.000001:
        return 0.0

    swing = current.normalized().rotation_difference(desired.normalized())
    matrix = parent.matrix.copy()
    rotated = swing.to_matrix() @ matrix.to_3x3()
    result = rotated.to_4x4()
    result.translation = parent.head
    parent.matrix = result
    bpy.context.view_layer.update()

    return (armature.pose.bones[child_name].head - target_child_head).length


def solve_two_bone_joint(
    root: Vector,
    requested_end: Vector,
    length_a: float,
    length_b: float,
    pole_hint: Vector,
) -> tuple[Vector, Vector]:
    """Return a reachable joint and end point for a two-segment chain."""
    to_end = requested_end - root
    if to_end.length <= 0.000001:
        to_end = Vector((0.0, 0.0, -1.0))
    direction = to_end.normalized()

    min_distance = abs(length_a - length_b) + 0.0001
    max_distance = max(length_a + length_b - 0.0001, min_distance)
    distance = min(max(to_end.length, min_distance), max_distance)
    end = root + direction * distance

    along = (
        length_a * length_a
        - length_b * length_b
        + distance * distance
    ) / (2.0 * distance)
    height_sq = max(length_a * length_a - along * along, 0.0)
    height = math.sqrt(height_sq)

    pole = pole_hint - direction * pole_hint.dot(direction)
    if pole.length <= 0.000001:
        fallback = Vector((1.0, 0.0, 0.0))
        if abs(direction.dot(fallback)) > 0.95:
            fallback = Vector((0.0, 1.0, 0.0))
        pole = fallback - direction * fallback.dot(direction)
    pole.normalize()

    joint = root + direction * along + pole * height
    return joint, end


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


def rest_snapshot(armature: bpy.types.Object) -> dict[str, Vector]:
    return {name: pose_head(armature, name) for name in REQUIRED_BONES}


def joint_length(rest: dict[str, Vector], a: str, b: str) -> float:
    return (rest[b] - rest[a]).length


def apply_body_phrase(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
    pose: dict,
) -> None:
    side = axes["side"]
    up = axes["up"]
    forward = axes["forward"]

    leg_length = (
        joint_length(rest, "Upper_Leg_L", "Lower_Leg_L")
        + joint_length(rest, "Lower_Leg_L", "Foot_L")
    )
    hip_width = joint_length(rest, "Upper_Leg_L", "Upper_Leg_R")
    plie = float(pose["plie"])
    cross = float(pose["cross"])

    # Support is left. The pelvis shifts over it before descending.
    support_shift = side * hip_width * 0.10 * cross
    pelvis_drop = -up * leg_length * 0.085 * plie
    translate_pose_bone_world(
        armature.pose.bones["Hips"],
        support_shift + pelvis_drop,
    )
    bpy.context.view_layer.update()

    rotate_pose_bone_world(
        armature.pose.bones["Spine 1"], side, float(pose["torso_deg"])
    )
    bpy.context.view_layer.update()
    rotate_pose_bone_world(
        armature.pose.bones["Chest"], side, float(pose["chest_deg"])
    )
    bpy.context.view_layer.update()
    rotate_pose_bone_world(
        armature.pose.bones["Head"], side, float(pose["head_deg"])
    )
    bpy.context.view_layer.update()

    # A tiny forward carriage accompanies the acknowledgement without folding
    # the waist. It is derived from the inferred facing axis.
    if plie > 0.0:
        translate_pose_bone_world(
            armature.pose.bones["Chest"],
            forward * leg_length * 0.006 * plie,
        )
        bpy.context.view_layer.update()


def apply_leg_chain(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
    pose: dict,
) -> list[float]:
    side = axes["side"]
    up = axes["up"]
    forward = axes["forward"]
    cross = float(pose["cross"])

    errors: list[float] = []
    hip_width = joint_length(rest, "Upper_Leg_L", "Upper_Leg_R")
    total_leg = (
        joint_length(rest, "Upper_Leg_L", "Lower_Leg_L")
        + joint_length(rest, "Lower_Leg_L", "Foot_L")
    )

    for left in (True, False):
        suffix = "L" if left else "R"
        side_sign = 1.0 if left else -1.0
        hip_name = f"Upper_Leg_{suffix}"
        knee_name = f"Lower_Leg_{suffix}"
        foot_name = f"Foot_{suffix}"
        toe_name = f"Toes_{suffix}"

        ankle_target = rest[foot_name].copy()
        if not left:
            # Working/right foot travels inward and slightly behind before the
            # plié. No explicit knee-out target exists; turnout comes from the
            # foot line plus the two-bone pole direction.
            ankle_target += side * hip_width * 1.05 * cross
            ankle_target -= forward * total_leg * 0.045 * cross

        length_a = joint_length(rest, hip_name, knee_name)
        length_b = joint_length(rest, knee_name, foot_name)
        # The knee plane follows the turned-out toe line with only a modest
        # lateral component. This avoids recreating the old frog/squat pose
        # through an overly lateral IK pole.
        pole_hint = (
            forward * 0.78
            + side * side_sign * 0.35
            - up * 0.15
        ).normalized()

        knee_target, reachable_ankle = solve_two_bone_joint(
            pose_head(armature, hip_name),
            ankle_target,
            length_a,
            length_b,
            pole_hint,
        )
        errors.append(
            aim_parent_to_child(
                armature, hip_name, knee_name, knee_target
            )
        )
        errors.append(
            aim_parent_to_child(
                armature, knee_name, foot_name, reachable_ankle
            )
        )

        foot_to_toe = rest[toe_name] - rest[foot_name]
        vertical = up * foot_to_toe.dot(up)
        horizontal_length = max(
            (foot_to_toe - vertical).length,
            0.001,
        )
        turnout_direction = (
            forward * 0.92 + side * side_sign * 0.38
        ).normalized()
        toe_target = (
            pose_head(armature, foot_name)
            + turnout_direction * horizontal_length
            + vertical
        )
        errors.append(
            aim_parent_to_child(
                armature, foot_name, toe_name, toe_target
            )
        )

    return errors


def arm_target(
    shoulder_center: Vector,
    side: Vector,
    up: Vector,
    forward: Vector,
    side_sign: float,
    reach: float,
    shape_name: str,
) -> tuple[Vector, Vector]:
    shape = ARM_SHAPES[shape_name]
    hand = (
        shoulder_center
        + side * side_sign * reach * float(shape["hand_side"])
        + forward * reach * float(shape["hand_forward"])
        - up * reach * float(shape["hand_down"])
    )
    # The elbow hint is deliberately not collinear with the hand target.
    # In OPEN, an outward-heavy pole projects behind the torso; this hint
    # keeps the elbow in the audience-facing half-space while preserving
    # the rounded classical arm line.
    elbow_hint = (
        side * side_sign * float(shape["elbow_side"])
        + forward * float(shape["elbow_forward"])
        - up * float(shape["elbow_down"])
    ).normalized()
    return hand, elbow_hint


def apply_arm_chain(
    armature: bpy.types.Object,
    axes: dict[str, Vector],
    rest: dict[str, Vector],
    pose: dict,
) -> list[float]:
    side = axes["side"]
    up = axes["up"]
    forward = axes["forward"]
    shape_name = str(pose["arm_shape"])

    left_shoulder = pose_head(armature, "Upper_Arm_L")
    right_shoulder = pose_head(armature, "Upper_Arm_R")
    shoulder_center = (left_shoulder + right_shoulder) * 0.5

    errors: list[float] = []
    for left in (True, False):
        suffix = "L" if left else "R"
        side_sign = 1.0 if left else -1.0
        upper = f"Upper_Arm_{suffix}"
        lower = f"Lower_Arm_{suffix}"
        hand = f"Hand_{suffix}"
        middle = f"Middle_{suffix}"

        length_a = joint_length(rest, upper, lower)
        length_b = joint_length(rest, lower, hand)
        reach = length_a + length_b
        hand_target, pole_hint = arm_target(
            shoulder_center,
            side,
            up,
            forward,
            side_sign,
            reach,
            shape_name,
        )

        elbow_target, reachable_hand = solve_two_bone_joint(
            pose_head(armature, upper),
            hand_target,
            length_a,
            length_b,
            pole_hint,
        )
        errors.append(
            aim_parent_to_child(
                armature, upper, lower, elbow_target
            )
        )
        errors.append(
            aim_parent_to_child(
                armature, lower, hand, reachable_hand
            )
        )

        # Hand/fingers continue the forearm tangent instead of receiving an
        # independent wrist Euler angle.
        hand_head = pose_head(armature, hand)
        elbow_head = pose_head(armature, lower)
        tangent = (hand_head - elbow_head).normalized()
        inward = -side * side_sign
        finish_direction = (
            tangent * 0.96 + inward * 0.10 - up * 0.04
        ).normalized()
        hand_to_middle = joint_length(rest, hand, middle)
        middle_target = hand_head + finish_direction * hand_to_middle
        errors.append(
            aim_parent_to_child(
                armature, hand, middle, middle_target
            )
        )

    return errors


def key_required_bones(armature: bpy.types.Object, frame: int) -> None:
    for bone_name in REQUIRED_BONES:
        pb = armature.pose.bones[bone_name]
        pb.rotation_mode = "QUATERNION"
        pb.keyframe_insert(
            data_path="rotation_quaternion", frame=frame, group=bone_name
        )
        pb.keyframe_insert(
            data_path="location", frame=frame, group=bone_name
        )


def capture_landmarks(armature: bpy.types.Object) -> dict:
    names = [
        "Hips", "Head",
        "Upper_Arm_L", "Lower_Arm_L", "Hand_L",
        "Upper_Arm_R", "Lower_Arm_R", "Hand_R",
        "Upper_Leg_L", "Lower_Leg_L", "Foot_L", "Toes_L",
        "Upper_Leg_R", "Lower_Leg_R", "Foot_R", "Toes_R",
    ]
    return {name: vec3(pose_head(armature, name)) for name in names}


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
    clear_pose(armature)
    axes = canonical_axes(armature)
    rest = rest_snapshot(armature)

    if ACTION_NAME in bpy.data.actions:
        bpy.data.actions.remove(bpy.data.actions[ACTION_NAME])

    action = bpy.data.actions.new(ACTION_NAME)
    action.use_fake_user = True
    armature.animation_data_create()
    armature.animation_data.action = action

    bpy.context.scene.render.fps = FPS
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = END_FRAME

    pose_report = []
    max_aim_error = 0.0
    for pose in POSES:
        clear_pose(armature)
        apply_body_phrase(armature, axes, rest, pose)
        leg_errors = apply_leg_chain(armature, axes, rest, pose)
        arm_errors = apply_arm_chain(armature, axes, rest, pose)
        frame = int(pose["frame"])
        key_required_bones(armature, frame)
        all_errors = leg_errors + arm_errors
        pose_max_error = max(all_errors) if all_errors else 0.0
        max_aim_error = max(max_aim_error, pose_max_error)
        pose_report.append({
            "frame": frame,
            "name": pose["name"],
            "arm_shape": pose["arm_shape"],
            "plie": pose["plie"],
            "cross": pose["cross"],
            "max_aim_error": round(pose_max_error, 7),
            "landmarks": capture_landmarks(armature),
        })

    configure_interpolation(action)
    bpy.context.scene.frame_set(1)

    if blend_output is not None:
        blend_output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(blend_output))

    export_glb(output_path)

    report = {
        "phase": "10.4.2.1",
        "authoring_model": "rig-aware joint targets + two-bone solve",
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
        "canonical_axes": {name: vec3(axis) for name, axis in axes.items()},
        "poses": pose_report,
        "max_aim_error": round(max_aim_error, 7),
        "bone_axes": bone_axes_report(armature),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("PHASE10_4_2=PASS")
    print(f"ARMATURE={armature.name}")
    print(f"ACTION={ACTION_NAME}")
    print(f"MAX_AIM_ERROR={max_aim_error:.7f}")
    print(f"OUTPUT={output_path}")
    print(f"REPORT={report_path}")


if __name__ == "__main__":
    main()
