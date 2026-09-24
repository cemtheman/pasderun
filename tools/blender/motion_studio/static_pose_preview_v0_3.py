"""One-frame final-Rig arm geometry proof, preview and numerical residuals.

No source-rig retargeting, keyframes, export, gameplay, or production changes.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


MOTION_TOOLS = Path(__file__).resolve().parents[2] / "motion_studio"
sys.path.insert(0, str(MOTION_TOOLS))
from rig_calibration import validate_calibration  # noqa: E402
from static_pose import solve_static_pose  # noqa: E402


def args_from_blender():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def align_joint(armature, bone_name, child_name, target_direction):
    """Shortest geometric rotation about an actual joint center in armature space."""
    bpy.context.view_layer.update()
    bone = armature.pose.bones[bone_name]
    child = armature.pose.bones[child_name]
    head = bone.head.copy()
    current = (child.head - head).normalized()
    target = Vector(target_direction).normalized()
    require(current.length > 0.99 and target.length > 0.99, f"{bone_name}: degenerate direction")
    rotation = current.rotation_difference(target).to_matrix().to_4x4()
    bone.matrix = Matrix.Translation(head) @ rotation @ Matrix.Translation(-head) @ bone.matrix.copy()
    bpy.context.view_layer.update()


def apply_solution(armature, solution):
    residuals = {}
    for side, arm in solution["arms"].items():
        upper, lower, hand = arm["bone_names"]
        for name, expected in ((upper, arm["shoulder"]), (lower, arm["elbow"]), (hand, arm["wrist"])):
            require(name in armature.pose.bones, f"Missing final Rig bone: {name}")
        shoulder = Vector(arm["shoulder"])
        require((armature.pose.bones[upper].head - shoulder).length < 1e-4,
                f"{side}: final Rig differs from calibrated rest shoulder")
        align_joint(armature, upper, lower, Vector(arm["elbow"]) - shoulder)
        elbow_error = (armature.pose.bones[lower].head - Vector(arm["elbow"])).length
        require(elbow_error <= arm["arm_reach"] * 0.005,
                f"{side}: elbow residual {elbow_error:.6f} exceeds tolerance")
        align_joint(armature, lower, hand, Vector(arm["wrist"]) - Vector(arm["elbow"]))
        wrist_error = (armature.pose.bones[hand].head - Vector(arm["wrist"])).length
        require(wrist_error <= arm["arm_reach"] * 0.005,
                f"{side}: wrist residual {wrist_error:.6f} exceeds tolerance")
        residuals[side] = {"elbow": round(elbow_error, 8), "wrist": round(wrist_error, 8),
                           "tolerance": round(arm["arm_reach"] * 0.005, 8)}
    return residuals


def render_views(armature, calibration, output):
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x = 600
    scene.render.resolution_y = 600
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.show_cavity = True
    head = Vector(calibration["canonical_bones"]["head"]["head_local"])
    left_foot = Vector(calibration["canonical_bones"]["left_foot"]["head_local"])
    right_foot = Vector(calibration["canonical_bones"]["right_foot"]["head_local"])
    foot = (left_foot + right_foot) * 0.5
    frame = calibration["anatomical_frame"]
    up = Vector(frame["up"])
    height = max((head - foot).dot(up), 0.1)
    center_local = foot + up * height * 0.52
    camera_data = bpy.data.cameras.new("MotionStudioV03Camera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = height * 1.38
    camera = bpy.data.objects.new("MotionStudioV03Camera", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    center_world = armature.matrix_world @ center_local
    previews = {}
    for name, direction in (("front", frame["front"]), ("side", frame["left"])):
        vector = (armature.matrix_world.to_3x3() @ Vector(direction)).normalized()
        camera.location = center_world + vector * height * 3
        camera.rotation_euler = (center_world - camera.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = str(output / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        require(Path(scene.render.filepath).is_file(), f"Missing {name} preview")
        previews[name] = scene.render.filepath
    return previews


def main():
    args = args_from_blender()
    repo = args.repo.resolve()
    output = args.output.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    target = json.loads(args.target.read_text(encoding="utf-8"))
    solution = solve_static_pose(target, calibration)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    bpy.context.scene.frame_set(1)
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    residuals = apply_solution(armature, solution)
    output.mkdir(parents=True, exist_ok=True)
    previews = render_views(armature, calibration, output)
    blend_path = output / "static_pose_v0_3.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report = {"status": "GEOMETRY_PASS_VISUAL_REVIEW_REQUIRED", "pose_id": solution["pose_id"],
              "source_glb_sha256": solution["source_glb_sha256"], "residuals": residuals,
              "previews": previews, "blend": str(blend_path),
              "limits": "No contact, balance, joint-limit or aesthetic approval in v0.3"}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("MOTION_STUDIO_V0_3_GEOMETRY=PASS_VISUAL_REVIEW_REQUIRED")
    print(f"REPORT={output / 'report.json'}")
    print(f"FRONT={previews['front']}")
    print(f"SIDE={previews['side']}")


if __name__ == "__main__":
    main()
