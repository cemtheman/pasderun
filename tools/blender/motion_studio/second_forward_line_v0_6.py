"""Render a descending, forward-moving second-position line for review."""

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
from accepted_arm_visual_v0_6 import align_hand_tips, measured_hand_mesh_projection  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from second_elbow_line import solve_second_forward_line  # noqa: E402
from static_pose import dot, sub  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "calibration", "reference", "source-profile", "output"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    repo, output = args.repo.resolve(), args.output.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    require(reference == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
            "Reference differs from accepted source bytes")
    original = joint_targets(reference, calibration, "second")
    candidate, search = solve_second_forward_line(original, calibration["anatomical_frame"])

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
    residuals = apply_solution(armature, candidate)
    hands = align_hand_tips(armature, candidate)
    projection = measured_hand_mesh_projection(armature, calibration)
    require(projection["projected_gap_armature_units"] >= 0,
            "Second-position hand mesh projection unexpectedly overlaps")
    frame = calibration["anatomical_frame"]
    lines = {}
    for side in ("left", "right"):
        old, new = original["arms"][side], candidate["arms"][side]
        lines[side] = {
            "old_shoulder_minus_elbow_up": round(dot(sub(old["shoulder"], old["elbow"]), frame["up"]), 8),
            "new_shoulder_minus_elbow_up": round(dot(sub(new["shoulder"], new["elbow"]), frame["up"]), 8),
            "new_elbow_minus_wrist_up": round(dot(sub(new["elbow"], new["wrist"]), frame["up"]), 8),
            "new_elbow_anterior_to_shoulder": round(dot(sub(new["elbow"], new["shoulder"]), frame["front"]), 8),
            "new_wrist_anterior_to_elbow": round(dot(sub(new["wrist"], new["elbow"]), frame["front"]), 8)
        }
        require(lines[side]["new_shoulder_minus_elbow_up"] > 0 and
                lines[side]["new_elbow_minus_wrist_up"] > 0 and
                lines[side]["new_elbow_anterior_to_shoulder"] > 0 and
                lines[side]["new_wrist_anterior_to_elbow"] > 0,
                f"{side}: descending, forward-moving second-position line not achieved")
    output.mkdir(parents=True, exist_ok=True)
    previews = render_views(armature, calibration, output, prefix="second_forward")
    blend = output / "second_forward_line_v0_6.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report_path = output / "report.json"
    report_path.write_text(json.dumps({
        "status": "SECOND_FORWARD_LINE_CANDIDATE_VISUAL_REVIEW_REQUIRED",
        "source_profile_sha256": reference["source_profile_sha256"],
        "source_glb_sha256": reference["source_glb_sha256"],
        "arm_lines": lines, "search_diagnostics": search,
        "hand_mesh_projection": projection,
        "residuals": residuals, "hand_tip_residuals": hands,
        "previews": previews, "blend": str(blend),
        "limits": "Static second-position candidate only; the 20-degree side-turn and "
                  "10-degree elbow-bend limits select a visual probe, not ballet technique. "
                  "No temporal solve, measured joint-limit gate or ballet-teacher approval."
    }, indent=2) + "\n", encoding="utf-8")
    print("MOTION_STUDIO_SECOND_FORWARD=CANDIDATE_VISUAL_REVIEW_REQUIRED")
    print(f"REPORT={report_path}")
    print(f"FRONT={previews['front']}")
    print(f"SIDE={previews['side']}")


if __name__ == "__main__":
    main()
