"""Key and inspect a short arm-only transition on the final Rig in Blender."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


MOTION_TOOLS = Path(__file__).resolve().parents[2] / "motion_studio"
sys.path.insert(0, str(MOTION_TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from arm_transition import solve_arm_transition  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


def args_from_blender():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def main():
    args = args_from_blender()
    repo, output = args.repo.resolve(), args.output.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    transition = solve_arm_transition(json.loads(args.target.read_text(encoding="utf-8")), calibration)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    scene = bpy.context.scene
    scene.render.fps = transition["fps"]
    scene.frame_start, scene.frame_end = 1, transition["duration_frames"]
    output.mkdir(parents=True, exist_ok=True)
    reports = []
    for item in transition["frames"]:
        frame = item["frame"]
        scene.frame_set(frame)
        for bone in armature.pose.bones:
            bone.matrix_basis = Matrix.Identity(4)
        for arm in item["arms"].values():
            for name in arm["bone_names"][:2]:
                armature.pose.bones[name].rotation_mode = "QUATERNION"
        bpy.context.view_layer.update()
        residuals = apply_solution(armature, {"arms": item["arms"]})
        for arm in item["arms"].values():
            for name in arm["bone_names"][:2]:
                bone = armature.pose.bones[name]
                bone.keyframe_insert(data_path="rotation_quaternion", frame=frame)
        reports.append({"frame": frame, "solve_residuals": residuals})

    # A key at every frame is checked after Blender evaluates its own action.
    for item, report in zip(transition["frames"], reports):
        scene.frame_set(item["frame"])
        bpy.context.view_layer.update()
        report["playback_residuals"] = {}
        for side, arm in item["arms"].items():
            lower, hand = (armature.pose.bones[name] for name in arm["bone_names"][1:])
            elbow_error = (lower.head - Vector(arm["elbow"])).length
            wrist_error = (hand.head - Vector(arm["wrist"])).length
            tolerance = arm["arm_reach"] * 0.005
            require(elbow_error <= tolerance and wrist_error <= tolerance,
                    f"Frame {item['frame']} {side}: keyed playback residual exceeds tolerance")
            report["playback_residuals"][side] = {"elbow": round(elbow_error, 8), "wrist": round(wrist_error, 8)}
    previews = {}
    for frame in (1, (transition["duration_frames"] + 1)//2, transition["duration_frames"]):
        scene.frame_set(frame)
        previews[str(frame)] = render_views(armature, calibration, output, prefix=f"frame_{frame:02d}")
    scene.frame_set(1)
    blend_path = output / "arm_transition_v0_5.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report = {"status": "KEYED_GEOMETRY_PASS_VISUAL_REVIEW_REQUIRED",
              "transition_id": transition["transition_id"], "source_glb_sha256": transition["source_glb_sha256"],
              "fps": transition["fps"], "frames": reports, "previews": previews, "blend": str(blend_path),
              "limits": transition["limits"]}
    (output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("MOTION_STUDIO_V0_5_ARM_TRANSITION=PASS_VISUAL_REVIEW_REQUIRED")
    print(f"REPORT={output / 'report.json'}")
    print(f"BLEND={blend_path}")
    for frame, paths in previews.items():
        print(f"FRAME_{frame}_FRONT={paths['front']}")
        print(f"FRAME_{frame}_SIDE={paths['side']}")


if __name__ == "__main__":
    main()
