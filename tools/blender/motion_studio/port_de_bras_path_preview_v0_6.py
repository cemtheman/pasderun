"""Key a 49-sample arm-only geometry probe through three review candidates."""

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
from hand_clearance_candidate import shifted_solution  # noqa: E402
from port_de_bras_path import sample_port_de_bras  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from second_elbow_line import solve_second_forward_line  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "calibration", "reference", "source-profile", "clearance-report",
                 "en-avant-report", "second-report", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    repo, output = args.repo.resolve(), args.output.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    require(reference == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
            "Accepted reference differs from its exact Phase 10 source")
    reports = {"clearance": json.loads(args.clearance_report.read_text(encoding="utf-8")),
               "en_avant": json.loads(args.en_avant_report.read_text(encoding="utf-8")),
               "second": json.loads(args.second_report.read_text(encoding="utf-8"))}
    for name, report in reports.items():
        require(report.get("source_profile_sha256") == reference["source_profile_sha256"] and
                report.get("source_glb_sha256") == reference["source_glb_sha256"],
                f"{name}: source report digest mismatch")
    first_report = reports["clearance"]["poses"]["bras_bas"]
    shift_first = first_report["outward_shift_per_wrist_armature_units"]
    shift_middle = reports["en_avant"]["outward_shift_per_wrist_armature_units"]
    require(first_report["candidate_projection"]["projected_gap_armature_units"] >= 0 and
            reports["en_avant"]["hand_mesh_projection"]["projected_gap_armature_units"] >= 0 and
            reports["second"]["hand_mesh_projection"]["projected_gap_armature_units"] >= 0,
            "A static candidate already overlaps in frontal hand projection")
    frame = calibration["anatomical_frame"]
    start = shifted_solution(joint_targets(reference, calibration, "bras_bas"), frame, shift_first)
    middle = shifted_solution(joint_targets(reference, calibration, "en_avant"),
                              frame, shift_middle, "body_outward")
    end, second_diagnostics = solve_second_forward_line(
        joint_targets(reference, calibration, "second"), frame)
    require(all(abs(second_diagnostics[side]["side_turn_deg"] -
                    reports["second"]["search_diagnostics"][side]["side_turn_deg"]) < 1e-5
                and all(abs(a - b) < 1e-5 for a, b in zip(
                    second_diagnostics[side]["wrist_shift_armature_units"],
                    reports["second"]["search_diagnostics"][side]["wrist_shift_armature_units"]))
                for side in ("left", "right")), "Cannot reproduce reviewed second-position candidate")
    samples = sample_port_de_bras({"bras_bas": start, "en_avant": middle, "second": end}, frame)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects
                 if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    scene = bpy.context.scene
    scene.frame_start, scene.frame_end = 1, samples[-1]["frame"]
    scene.render.fps = 24  # Review playback only; not authored choreography timing.
    output.mkdir(parents=True, exist_ok=True)

    for sample in samples:
        scene.frame_set(sample["frame"])
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
                    data_path="rotation_quaternion", frame=sample["frame"])

    playback = []
    for sample in samples:
        scene.frame_set(sample["frame"])
        bpy.context.view_layer.update()
        errors = {}
        for side, arm in sample["arms"].items():
            elbow = armature.pose.bones[arm["bone_names"][1]].head
            wrist = armature.pose.bones[arm["bone_names"][2]].head
            hand = armature.pose.bones[arm["bone_names"][2]].tail
            tolerance = arm["arm_reach"] * .005
            errors[side] = {"elbow": round((elbow - Vector(arm["elbow"])).length, 8),
                            "wrist": round((wrist - Vector(arm["wrist"])).length, 8),
                            "hand": round((hand - Vector(arm["hand"])).length, 8)}
            require(all(value <= tolerance for value in errors[side].values()),
                    f"Frame {sample['frame']} {side}: keyed playback joint residual exceeds tolerance")
        projection = measured_hand_mesh_projection(armature, calibration)
        playback.append({"frame": sample["frame"], "from": sample["from"], "to": sample["to"],
                         "playback_residuals": errors, "inward_flexion": sample["inward_flexion"],
                         "hand_projected_gap_armature_units": projection["projected_gap_armature_units"]})
    previews = {}
    for frame_number in (1, 13, 25, 37, 49):
        scene.frame_set(frame_number)
        previews[str(frame_number)] = render_views(armature, calibration, output,
                                                   prefix=f"port_de_bras_{frame_number:02d}")
    scene.frame_set(1)
    blend = output / "port_de_bras_path_probe_v0_6.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    worst = min(playback, key=lambda item: item["hand_projected_gap_armature_units"])
    report_path = output / "report.json"
    report_path.write_text(json.dumps({
        "status": ("PATH_PROBE_VISUAL_REVIEW_REQUIRED" if worst["hand_projected_gap_armature_units"] >= 0
                   else "PATH_PROBE_FRONT_HAND_OVERLAP"),
        "source_profile_sha256": reference["source_profile_sha256"],
        "source_glb_sha256": reference["source_glb_sha256"],
        "frame_grid": "49 integer samples; frames 1, 25, 49 are exact static candidates; not choreography timing",
        "worst_projected_hand_gap": worst, "frames": playback, "previews": previews, "blend": str(blend),
        "limits": "Arm-only sampled geometry probe. Positive frontal gap does not establish three-dimensional "
                  "collision freedom. No measured hinge axis, ballet review, movement approval or runtime export."
    }, indent=2) + "\n", encoding="utf-8")
    print(f"MOTION_STUDIO_PORT_DE_BRAS={json.loads(report_path.read_text())['status']}")
    print(f"REPORT={report_path}")
    for frame_number, paths in previews.items():
        print(f"FRAME_{frame_number}_FRONT={paths['front']}")
        print(f"FRAME_{frame_number}_SIDE={paths['side']}")
    print(f"BLEND={blend}")


if __name__ == "__main__":
    main()
