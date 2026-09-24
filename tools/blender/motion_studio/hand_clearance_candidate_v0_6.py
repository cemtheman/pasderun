"""Bounded measured-hand-clearance pose candidate on the final Rig.

This generates only four review PNGs, a report and a local Blend with the
last static pose. The accepted reference remains unmodified.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix

MOTION_TOOLS = Path(__file__).resolve().parents[2] / "motion_studio"
sys.path.insert(0, str(MOTION_TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from accepted_arm_reference import extract_accepted_arm_reference  # noqa: E402
from accepted_arm_visual import joint_targets  # noqa: E402
from hand_clearance_candidate import shifted_solution  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from accepted_arm_visual_v0_6 import align_hand_tips, measured_hand_mesh_projection  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


def pose_and_measure(armature, calibration, solution):
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    residuals = apply_solution(armature, solution)
    hand_residuals = align_hand_tips(armature, solution)
    projection = measured_hand_mesh_projection(armature, calibration)
    return residuals, hand_residuals, projection


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "calibration", "reference", "source-profile", "measurement", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    repo = args.repo.resolve()
    output = args.output.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    require(reference == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
            "Reference differs from accepted source bytes")
    measurement = json.loads(args.measurement.read_text(encoding="utf-8"))
    require(measurement.get("source_profile_sha256") == reference["source_profile_sha256"] and
            measurement.get("source_glb_sha256") == reference["source_glb_sha256"],
            "Mesh diagnostic source digest mismatch")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    bpy.context.scene.frame_set(1)
    output.mkdir(parents=True, exist_ok=True)
    poses = {}
    for pose in ("bras_bas", "en_avant"):
        original = joint_targets(reference, calibration, pose)
        baseline = measurement.get("poses", {}).get(pose, {}).get("hand_mesh_projection", {})
        required_gap = baseline.get("projected_gap_armature_units")
        require(isinstance(required_gap, (int, float)) and required_gap < 0,
                f"{pose}: expected a measured negative hand projection gap")
        _, _, measured = pose_and_measure(armature, calibration, original)
        require(abs(measured["projected_gap_armature_units"] - required_gap) < 1e-5,
                f"{pose}: current mesh differs from supplied diagnostic")
        shift = -required_gap / 2
        tolerance = original["arms"]["left"]["arm_reach"] * 0.005
        for iteration in range(1, 13):
            candidate = shifted_solution(original, calibration["anatomical_frame"], shift)
            residuals, hand_residuals, projected = pose_and_measure(armature, calibration, candidate)
            if projected["projected_gap_armature_units"] >= 0:
                break
            shift += max(-projected["projected_gap_armature_units"] / 2, tolerance)
        else:
            raise RuntimeError(f"{pose}: cannot clear hand projection in 12 measured corrections")
        views = render_views(armature, calibration, output, prefix=f"{pose}_clearance")
        poses[pose] = {"outward_shift_per_wrist_armature_units": round(shift, 8),
                       "iterations": iteration, "baseline_projection": measured,
                       "candidate_projection": projected, "residuals": residuals,
                       "hand_tip_residuals": hand_residuals, "previews": views}
    blend_path = output / "hand_clearance_candidate_v0_6.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report_path = output / "report.json"
    report_path.write_text(json.dumps({
        "status": "STATIC_CLEARANCE_CANDIDATE_VISUAL_REVIEW_REQUIRED",
        "reference_id": reference["reference_id"],
        "source_profile_sha256": reference["source_profile_sha256"],
        "source_glb_sha256": reference["source_glb_sha256"],
        "poses": poses, "blend": str(blend_path),
        "limits": "Frontal hand-mesh separation only. No guarantee against 3D collisions, limb/body "
                  "contact, ballet quality or temporal smoothness. Second position is unchanged."
    }, indent=2) + "\n", encoding="utf-8")
    print("MOTION_STUDIO_HAND_CLEARANCE=CANDIDATE_VISUAL_REVIEW_REQUIRED")
    print(f"REPORT={report_path}")
    for pose, result in poses.items():
        print(f"{pose.upper()}_GAP={result['candidate_projection']['projected_gap_armature_units']}")
        for view, path in result["previews"].items():
            print(f"{pose.upper()}_{view.upper()}={path}")


if __name__ == "__main__":
    main()
