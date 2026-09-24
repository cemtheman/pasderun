"""Render existing Phase 10 arm joint landmarks on the final Rig for review.

No keyframes, altered source assets, export, or motion approval are produced.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
from accepted_arm_reference import extract_accepted_arm_reference  # noqa: E402
from accepted_arm_visual import joint_targets  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


def align_hand_tips(armature, solution):
    """Aim each measured hand bone tail at its accepted hand landmark."""
    residuals = {}
    for side, arm in solution["arms"].items():
        bone = armature.pose.bones[arm["bone_names"][2]]
        bpy.context.view_layer.update()
        head = bone.head.copy()
        target = Vector(arm["hand"])
        require((head - Vector(arm["wrist"])).length <= arm["arm_reach"] * 0.005,
                f"{side}: hand head differs from solved wrist")
        current = bone.tail - head
        desired = target - head
        require(current.length > 1e-8 and desired.length > 1e-8, f"{side}: degenerate hand direction")
        rotation = current.rotation_difference(desired).to_matrix().to_4x4()
        bone.matrix = Matrix.Translation(head) @ rotation @ Matrix.Translation(-head) @ bone.matrix.copy()
        bpy.context.view_layer.update()
        error = (bone.tail - target).length
        tolerance = arm["arm_reach"] * 0.005
        require(error <= tolerance, f"{side}: hand endpoint residual {error:.6f} exceeds tolerance")
        residuals[side] = round(error, 8)
    return residuals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--source-profile", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    repo = args.repo.resolve()
    output = args.output.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    require(reference == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
            "Reference JSON differs from exact accepted source profile")
    pose_order = ("bras_bas", "en_avant", "second")
    solutions = {pose: joint_targets(reference, calibration, pose) for pose in pose_order}

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    bpy.context.scene.frame_set(1)
    output.mkdir(parents=True, exist_ok=True)

    report_poses = {}
    for pose in pose_order:
        for bone in armature.pose.bones:
            bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        residuals = apply_solution(armature, solutions[pose])
        hand_residuals = align_hand_tips(armature, solutions[pose])
        previews = render_views(armature, calibration, output, prefix=pose)
        report_poses[pose] = {"residuals": residuals, "hand_tip_residuals": hand_residuals,
                              "previews": previews}

    blend_path = output / "accepted_arm_visual_v0_6.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report = {
        "status": "GEOMETRY_PASS_VISUAL_REVIEW_REQUIRED",
        "reference_id": reference["reference_id"],
        "source_profile_sha256": reference["source_profile_sha256"],
        "source_glb_sha256": reference["source_glb_sha256"],
        "poses": report_poses, "blend": str(blend_path),
        "limits": "Static arm joint centers and hand bone tip direction only. Fingers, ballet quality, teacher review, "
                  "contact, balance and motion timing are untested. The saved Blend shows only second position."
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("MOTION_STUDIO_V0_6_ACCEPTED_ARM=PASS_VISUAL_REVIEW_REQUIRED")
    print(f"REPORT={report_path}")
    for pose in pose_order:
        for view, path in report_poses[pose]["previews"].items():
            print(f"{pose.upper()}_{view.upper()}={path}")
    print(f"BLEND={blend_path}")


if __name__ == "__main__":
    main()
