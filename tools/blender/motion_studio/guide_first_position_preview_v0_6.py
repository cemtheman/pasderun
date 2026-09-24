"""Render a bounded, lower first-position candidate from the user's guide."""

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
from first_position_candidate import guide_first_position  # noqa: E402
from hand_clearance_candidate import shifted_solution  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose import dot  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "calibration", "reference", "source-profile", "clearance-report",
                 "en-avant-report", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    repo, output = args.repo.resolve(), args.output.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    require(reference == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
            "Reference differs from exact accepted Phase 10 source")
    clearance = json.loads(args.clearance_report.read_text(encoding="utf-8"))
    en_avant = json.loads(args.en_avant_report.read_text(encoding="utf-8"))
    for name, report in (("clearance", clearance), ("en_avant", en_avant)):
        require(report.get("source_profile_sha256") == reference["source_profile_sha256"] and
                report.get("source_glb_sha256") == reference["source_glb_sha256"],
                f"{name}: source digest mismatch")
    require(clearance["poses"]["bras_bas"]["candidate_projection"]["projected_gap_armature_units"] >= 0
            and en_avant["hand_mesh_projection"]["projected_gap_armature_units"] >= 0,
            "Expected previously separated endpoint poses")
    anatomical_frame = calibration["anatomical_frame"]
    low = shifted_solution(joint_targets(reference, calibration, "bras_bas"), anatomical_frame,
                           clearance["poses"]["bras_bas"]["outward_shift_per_wrist_armature_units"])
    high = shifted_solution(joint_targets(reference, calibration, "en_avant"), anatomical_frame,
                            en_avant["outward_shift_per_wrist_armature_units"], "body_outward")
    spine_mid_height = dot(calibration["canonical_bones"]["spine_mid"]["head_local"],
                           anatomical_frame["up"])
    candidate = guide_first_position(low, high, anatomical_frame,
                                      navel_region_height=spine_mid_height)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects
                 if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    bpy.context.scene.frame_set(1)
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    residuals = apply_solution(armature, candidate)
    hand_residuals = align_hand_tips(armature, candidate)
    projection = measured_hand_mesh_projection(armature, calibration)
    output.mkdir(parents=True, exist_ok=True)
    previews = render_views(armature, calibration, output, prefix="guide_first")
    blend = output / "guide_first_position_v0_6.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    up = anatomical_frame["up"]
    heights = {side: {"preparatory_wrist": dot(low["arms"][side]["wrist"], up),
                      "first_candidate_wrist": dot(candidate["arms"][side]["wrist"], up),
                      "old_high_en_avant_wrist": dot(high["arms"][side]["wrist"], up)}
               for side in ("left", "right")}
    anchors = {name: round(dot(calibration["canonical_bones"][name]["head_local"], up), 8)
               for name in ("pelvis", "spine_lower", "spine_mid", "chest")}
    report_path = output / "report.json"
    status = ("FIRST_POSITION_STATIC_VISUAL_REVIEW_REQUIRED" if
              projection["projected_gap_armature_units"] >= 0 else
              "FIRST_POSITION_FRONT_HAND_OVERLAP")
    report_path.write_text(json.dumps({
        "status": status, "source_profile_sha256": reference["source_profile_sha256"],
        "source_glb_sha256": reference["source_glb_sha256"],
        "guide_pdf_sha256": "2d6321bf92dd97014fb86555bc30426772e9a34e0527e7bf397339fa3648793d",
        "height_method": "Wrist at calibrated spine_mid bone head elevation; torso proxy, not a navel measurement",
        "height_bounds_armature_units": heights,
        "calibrated_rig_bone_head_heights_armature_units": anchors,
        "hand_mesh_projection": projection, "residuals": residuals,
        "hand_tip_residuals": hand_residuals, "previews": previews, "blend": str(blend),
        "limits": "The calibrated spine_mid bone head sets a bounded navel-region height "
                  "hypothesis, NOT a measured navel landmark. Front/side form needs review. "
                  "This static arm-only probe does not author the 49-frame path or alter feet."
    }, indent=2) + "\n", encoding="utf-8")
    print(f"MOTION_STUDIO_GUIDE_FIRST={status}")
    print(f"REPORT={report_path}")
    print(f"FRONT={previews['front']}")
    print(f"SIDE={previews['side']}")
    print(f"BLEND={blend}")


if __name__ == "__main__":
    main()
