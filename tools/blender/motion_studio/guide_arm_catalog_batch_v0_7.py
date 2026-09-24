"""Build all beginner-guide arm shapes and reversible connecting clips on final Rig."""

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
from accepted_arm_visual_v0_6 import align_hand_tips, measured_hand_mesh_projection  # noqa: E402
from first_position_candidate import guide_first_position  # noqa: E402
from guide_arm_catalog import (combine_arm_positions, crown_position,
                               route_arm_positions, sample_arm_transition)  # noqa: E402
from hand_clearance_candidate import shifted_solution  # noqa: E402
from port_de_bras_path import sample_port_de_bras  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from second_elbow_line import solve_second_forward_line  # noqa: E402
from static_pose import dot  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


def load_input(args):
    repo = args.repo.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    require(reference == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
            "Accepted reference differs from exact source profile")
    reports = [json.loads(p.read_text(encoding="utf-8")) for p in
               (args.clearance_report, args.en_avant_report, args.first_report, args.second_report)]
    require(all(r["source_profile_sha256"] == reference["source_profile_sha256"] and
                r["source_glb_sha256"] == reference["source_glb_sha256"] for r in reports),
            "Static source-report digest mismatch")
    require(reports[2]["status"] == "FIRST_POSITION_STATIC_VISUAL_REVIEW_REQUIRED" and
            reports[2]["height_method"].startswith("Wrist at calibrated spine_mid bone head elevation"),
            "Guide first report is not the screened lower first position")
    return repo, calibration, rig, reference, reports


def build_catalog(calibration, reference, reports, crown_lateral_fraction=.12):
    frame = calibration["anatomical_frame"]
    low = shifted_solution(joint_targets(reference, calibration, "bras_bas"), frame,
                           reports[0]["poses"]["bras_bas"]["outward_shift_per_wrist_armature_units"])
    high = shifted_solution(joint_targets(reference, calibration, "en_avant"), frame,
                            reports[1]["outward_shift_per_wrist_armature_units"], "body_outward")
    torso = dot(calibration["canonical_bones"]["spine_mid"]["head_local"], frame["up"])
    first = guide_first_position(low, high, frame, navel_region_height=torso)
    second, second_diag = solve_second_forward_line(joint_targets(reference, calibration, "second"), frame)
    require(all(abs(second_diag[side]["side_turn_deg"] -
                    reports[3]["search_diagnostics"][side]["side_turn_deg"]) < 1e-5
                for side in ("left", "right")), "Second reference cannot be reproduced")
    head_top = dot(calibration["canonical_bones"]["head"]["tail_local"], frame["up"])
    fifth = crown_position(second, frame, head_top,
                           lateral_fraction=crown_lateral_fraction)
    poses = {
        "bras_bas": low, "first": first, "second": second, "fifth_crown": fifth,
        "third_left_first": combine_arm_positions("third_left_first", first, second),
        "third_right_first": combine_arm_positions("third_right_first", second, first),
        "fourth_left_crown": combine_arm_positions("fourth_left_crown", fifth, second),
        "fourth_right_crown": combine_arm_positions("fourth_right_crown", second, fifth),
    }
    reviewed = sample_port_de_bras({"bras_bas": low, "first_position": first, "second": second}, frame,
                                    order=("bras_bas", "first_position", "second"),
                                    guide_clearance=.01, guide_opening_lead=.8,
                                    opening_arc_up_fraction=.19, opening_arc_front_fraction=.26)
    edges = {
        ("bras_bas", "first"): reviewed[:25],
        ("first", "second"): reviewed[24:],
    }
    for start, end in (("first", "fifth_crown"),
                       ("first", "third_left_first"), ("first", "third_right_first"),
                       ("third_left_first", "fourth_left_crown"),
                       ("third_right_first", "fourth_right_crown")):
        edges[(start, end)] = sample_arm_transition(poses[start], poses[end], frame)
    return poses, edges, head_top


def keyed_action(armature, name, samples, calibration, output, render=False):
    scene = bpy.context.scene
    armature.animation_data.action = None
    for frame_number, sample in enumerate(samples, 1):
        scene.frame_set(frame_number)
        for bone in armature.pose.bones:
            bone.matrix_basis = Matrix.Identity(4)
        for arm in sample["arms"].values():
            for bone_name in arm["bone_names"]:
                armature.pose.bones[bone_name].rotation_mode = "QUATERNION"
        bpy.context.view_layer.update()
        apply_solution(armature, sample)
        align_hand_tips(armature, sample)
        for arm in sample["arms"].values():
            for bone_name in arm["bone_names"]:
                armature.pose.bones[bone_name].keyframe_insert(
                    data_path="rotation_quaternion", frame=frame_number)
    action = armature.animation_data.action
    require(action is not None, f"{name}: no keyed action generated")
    action.name, action.use_fake_user = f"MS07_{name}", True
    measurements = []
    for frame_number, sample in enumerate(samples, 1):
        scene.frame_set(frame_number)
        bpy.context.view_layer.update()
        max_error = 0.0
        for arm in sample["arms"].values():
            upper, lower, hand = arm["bone_names"]
            for bone, target in ((lower, arm["elbow"]), (hand, arm["wrist"])):
                max_error = max(max_error, (armature.pose.bones[bone].head - Vector(target)).length)
            max_error = max(max_error, (armature.pose.bones[hand].tail - Vector(arm["hand"])).length)
            require(max_error <= arm["arm_reach"] * .005,
                    f"{name} frame {frame_number}: playback joint residual too high")
        projection = measured_hand_mesh_projection(armature, calibration)
        measurements.append({"sample": frame_number,
                             "hand_projected_gap": projection["projected_gap_armature_units"],
                             "maximum_joint_residual": round(max_error, 8)})
    previews = {}
    if render:
        scene.frame_set(len(samples) if len(samples) == 1 else (len(samples) + 1) // 2)
        previews = render_views(armature, calibration, output, prefix=name)
    return {"action": action.name, "samples": len(samples),
            "minimum_hand_gap": min(m["hand_projected_gap"] for m in measurements),
            "worst_frame": min(measurements, key=lambda m: m["hand_projected_gap"]),
            "maximum_joint_residual": max(m["maximum_joint_residual"] for m in measurements),
            "previews": previews}


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "calibration", "reference", "source-profile", "clearance-report",
                 "en-avant-report", "first-report", "second-report", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    repo, calibration, rig, reference, reports = load_input(args)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects
                 if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one calibrated final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    armature.animation_data_create()
    crown_trials = []
    for fraction in (.12, .15, .18, .22, .26):
        poses, edges, head_top = build_catalog(calibration, reference, reports, fraction)
        bpy.context.scene.frame_set(1)
        for bone in armature.pose.bones:
            bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        apply_solution(armature, poses["fifth_crown"])
        align_hand_tips(armature, poses["fifth_crown"])
        gap = measured_hand_mesh_projection(armature, calibration)["projected_gap_armature_units"]
        crown_trials.append({"lateral_arm_reach_fraction": fraction, "frontal_gap": gap})
        if gap >= 0:
            break
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 25
    # A convenient local review rate; the guide contains no motion timing.
    bpy.context.scene.render.fps = 24
    pose_report, clip_report = {}, {}
    for name, pose in poses.items():
        pose_report[name] = keyed_action(armature, "pose_" + name,
                                         [pose], calibration, output, render=True)
    for (start, end), samples in edges.items():
        forward = f"{start}_to_{end}"
        reverse = f"{end}_to_{start}"
        clip_report[forward] = keyed_action(armature, forward, samples,
                                            calibration, output, render=True)
        clip_report[reverse] = keyed_action(armature, reverse, samples[::-1],
                                            calibration, output)
    blend = output / "guide_arm_catalog_v0_7.blend"
    armature.animation_data.action = None
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    failures = [name for name, result in {**pose_report, **clip_report}.items()
                if result["minimum_hand_gap"] < 0]
    routes = {f"{start}_to_{end}": route_arm_positions(start, end, edges)
              for start in poses for end in poses if start != end}
    report = {
        "status": "CATALOG_FRONT_HAND_OVERLAP" if failures else "CATALOG_GEOMETRY_RENDERED",
        "source_profile_sha256": reference["source_profile_sha256"],
        "source_glb_sha256": reference["source_glb_sha256"],
        "guide_pdf_sha256": "2d6321bf92dd97014fb86555bc30426772e9a34e0527e7bf397339fa3648793d",
        "head_bone_tail_height": head_top,
        "crown_wrist_separation_trials": crown_trials,
        "poses": pose_report, "clips": clip_report, "pair_routes": routes,
        "front_overlap_names": failures, "blend": str(blend),
        "limits": "Eight arm-only candidate shapes, fourteen reversible connecting actions. "
                  "Mixed third/fourth are arm combinations; feet remain at rig rest. "
                  "Actions are a diagnostic review grid, not authored ballet timing. "
                  "No head/torso collision clearance or game export; fifth crown needs visual review."
    }
    path = output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"MOTION_STUDIO_GUIDE_ARM_CATALOG={report['status']}")
    print(f"REPORT={path}")
    print(f"BLEND={blend}")


if __name__ == "__main__":
    main()
