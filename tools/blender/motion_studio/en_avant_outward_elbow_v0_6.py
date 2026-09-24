"""Review en avant with an anatomical outward elbow bend and measured hand gap."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy

MOTION_TOOLS = Path(__file__).resolve().parents[2] / "motion_studio"
sys.path.insert(0, str(MOTION_TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from accepted_arm_reference import extract_accepted_arm_reference  # noqa: E402
from accepted_arm_visual import joint_targets  # noqa: E402
from hand_clearance_candidate import shifted_solution  # noqa: E402
from hand_clearance_candidate_v0_6 import pose_and_measure  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose import dot, sub  # noqa: E402
from static_pose_preview_v0_3 import render_views, require  # noqa: E402


def side_kink_deg(arm, frame):
    upper = sub(arm["elbow"], arm["shoulder"])
    lower = sub(arm["wrist"], arm["elbow"])
    a = [dot(upper, frame[axis]) for axis in ("up", "front")]
    b = [dot(lower, frame[axis]) for axis in ("up", "front")]
    scale = math.hypot(*a) * math.hypot(*b)
    require(scale > 1e-8, "Degenerate arm side-view projection")
    return round(math.degrees(math.acos(max(-1, min(1, dot(a, b) / scale)))), 6)


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "calibration", "reference", "source-profile", "clearance-report", "output"):
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
    baseline = json.loads(args.clearance_report.read_text(encoding="utf-8"))
    require(baseline.get("source_profile_sha256") == reference["source_profile_sha256"] and
            baseline.get("source_glb_sha256") == reference["source_glb_sha256"],
            "Clearance candidate source digest mismatch")
    old_pose = baseline.get("poses", {}).get("en_avant", {})
    shift = old_pose.get("outward_shift_per_wrist_armature_units")
    old_gap = old_pose.get("candidate_projection", {}).get("projected_gap_armature_units")
    require(isinstance(shift, (int, float)) and shift > 0 and
            isinstance(old_gap, (int, float)) and old_gap >= 0,
            "Expected a measured, separated en avant candidate")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    bpy.context.scene.frame_set(1)
    original = joint_targets(reference, calibration, "en_avant")
    frame = calibration["anatomical_frame"]
    reference_pole = shifted_solution(original, frame, shift)
    _, _, reproduced = pose_and_measure(armature, calibration, reference_pole)
    require(abs(reproduced["projected_gap_armature_units"] - old_gap) < 1e-5,
            "Cannot reproduce source clearance candidate on this mesh")

    tolerance = original["arms"]["left"]["arm_reach"] * 0.005
    for iteration in range(1, 13):
        candidate = shifted_solution(original, frame, shift, "body_outward")
        residuals, hand_residuals, projection = pose_and_measure(armature, calibration, candidate)
        if projection["projected_gap_armature_units"] >= 0:
            break
        shift += max(-projection["projected_gap_armature_units"] / 2, tolerance)
    else:
        raise RuntimeError("Outward elbow pole could not preserve measured hand separation")
    angles = {side: {"reference_pole_deg": side_kink_deg(reference_pole["arms"][side], frame),
                     "outward_pole_deg": side_kink_deg(candidate["arms"][side], frame)}
              for side in ("left", "right")}
    require(all(angles[s]["outward_pole_deg"] < angles[s]["reference_pole_deg"]
                for s in ("left", "right")), "Side-view elbow kink was not reduced")

    output.mkdir(parents=True, exist_ok=True)
    previews = render_views(armature, calibration, output, prefix="en_avant_outward")
    blend_path = output / "en_avant_outward_elbow_v0_6.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report_path = output / "report.json"
    report_path.write_text(json.dumps({
        "status": "EN_AVANT_ELBOW_CANDIDATE_VISUAL_REVIEW_REQUIRED",
        "source_profile_sha256": reference["source_profile_sha256"],
        "source_glb_sha256": reference["source_glb_sha256"],
        "outward_shift_per_wrist_armature_units": round(shift, 8),
        "iterations": iteration, "side_view_elbow_kink_deg": angles,
        "hand_mesh_projection": projection, "residuals": residuals,
        "hand_tip_residuals": hand_residuals, "previews": previews, "blend": str(blend_path),
        "limits": "Static en avant comparison only; the sideways bend changes elbow geometry, "
                  "not the hand-line choreography or second position. No ballet approval."
    }, indent=2) + "\n", encoding="utf-8")
    print("MOTION_STUDIO_EN_AVANT_OUTWARD=PASS_VISUAL_REVIEW_REQUIRED")
    print(f"REPORT={report_path}")
    print(f"FRONT={previews['front']}")
    print(f"SIDE={previews['side']}")


if __name__ == "__main__":
    main()
