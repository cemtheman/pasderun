"""Compose screened arm and candidate foot paths on one final Rig Action."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector

MOTION = Path(__file__).resolve().parents[2] / "motion_studio"
sys.path.insert(0, str(MOTION))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from accepted_arm_visual_v0_6 import align_hand_tips, measured_hand_mesh_projection  # noqa: E402
from guide_arm_catalog import route_arm_positions  # noqa: E402
from guide_arm_catalog_batch_v0_7 import build_catalog, load_input  # noqa: E402
from guide_foot_catalog import guide_foot_position, sample_foot_transition  # noqa: E402
from guide_foot_catalog_batch_v0_7 import apply_feet, evaluated_sole_heights, reset_pose  # noqa: E402
from rest_foot_contact_v0_4 import candidate_vertices, select_patch  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


# Left/right labels refer to the front foot and the corresponding mixed arm.
PAIRS = {
    "bras_bas_first_feet": ("bras_bas", "first"),
    "first": ("first", "first"),
    "second": ("second", "second"),
    "third_left": ("third_left_first", "third_left_front"),
    "third_right": ("third_right_first", "third_right_front"),
    "fourth_left": ("fourth_left_crown", "fourth_left_front"),
    "fourth_right": ("fourth_right_crown", "fourth_right_front"),
    "fifth_left": ("fifth_crown", "fifth_left_front"),
    "fifth_right": ("fifth_crown", "fifth_right_front"),
}


def shifted_arm_solution(sample, displacement):
    # Translating the pelvis moves shoulders and wrists in armature space.
    fields = ("shoulder", "elbow", "wrist", "hand")
    return {**sample, "arms": {
        side: {**arm, **{key: list(Vector(arm[key]) + displacement) for key in fields}}
        for side, arm in sample["arms"].items()}}


def pose_sample(arm, foot):
    return {"arm": arm, "foot": foot}


def render_feet_top(armature, calibration, output, prefix, sample):
    """Look down from below the skirt hem to expose the actual shoe mesh."""
    from mathutils import Vector
    frame = calibration["anatomical_frame"]
    up = Vector(frame["up"])
    heels = [Vector(leg["heel"]) for leg in sample["foot"]["legs"].values()]
    balls = [Vector(leg["ball"]) for leg in sample["foot"]["legs"].values()]
    points = heels + balls
    center = sum(points, Vector((0, 0, 0))) / len(points)
    lateral = [p.dot(Vector(frame["left"])) for p in points]
    forward = [p.dot(Vector(frame["front"])) for p in points]
    spread = max(max(lateral) - min(lateral), max(forward) - min(forward))
    scene = bpy.context.scene
    camera_data = bpy.data.cameras.new("MSFeetTopCamera")
    camera_data.type = "ORTHO"
    camera_data.ortho_scale = max(spread * 1.5, .2)
    camera = bpy.data.objects.new("MSFeetTopCamera", camera_data)
    scene.collection.objects.link(camera)
    camera.location = armature.matrix_world @ (center + up * max(spread, .25))
    camera.rotation_euler = ((armature.matrix_world @ center) - camera.location).to_track_quat(
        "-Z", "Y").to_euler()
    camera.data.clip_end = max(spread * 8, 3)
    scene.camera = camera
    filename = output / f"{prefix}_feet_top.png"
    scene.render.filepath = str(filename)
    bpy.ops.render.render(write_still=True)
    require(filename.is_file(), f"{prefix}: top shoe view missing")
    return str(filename)


def footprint(sample, frame):
    """Preserve actual target geometry in the report for comparable poses."""
    result = {}
    for side, leg in sample["foot"]["legs"].items():
        result[side] = {
            "heel_left_front": [Vector(leg["heel"]).dot(Vector(frame[key]))
                                for key in ("left", "front")],
            "ball_left_front": [Vector(leg["ball"]).dot(Vector(frame[key]))
                                for key in ("left", "front")],
            "target_toe_heading_degrees": leg["turnout_deg"],
        }
    return result


def combined_paths(arms, arm_edges, feet, frame):
    first = feet["first"]
    paths = {}
    # Each edge starts at the canonical first position, except the reversible
    # Bra Bas preparation. Fourth arms pass through third; feet use 49 samples.
    for name, (arm_name, foot_name) in PAIRS.items():
        if name == "first":
            continue
        if name == "bras_bas_first_feet":
            arm_samples = arm_edges[("bras_bas", "first")][::-1]
            foot_samples = [first] * len(arm_samples)
        elif name.startswith("fourth_"):
            side = name.split("_")[1]
            third = f"third_{side}_first"
            arm_samples = (arm_edges[("first", third)] +
                           arm_edges[(third, arm_name)][1:])
            foot_samples = sample_foot_transition(first, feet[foot_name], frame,
                                                   count=len(arm_samples))
        else:
            arm_samples = arm_edges[("first", arm_name)]
            foot_samples = sample_foot_transition(first, feet[foot_name], frame,
                                                   count=len(arm_samples))
        require(len(arm_samples) == len(foot_samples), f"{name}: path grid mismatch")
        paths[("first", name)] = [pose_sample(a, f) for a, f in zip(arm_samples, foot_samples)]
    return paths


def apply_both(armature, sample, calibration):
    reset_pose(armature)
    foot, arm = sample["foot"], sample["arm"]
    leg_error = apply_feet(armature, foot, calibration)
    shift = -Vector(calibration["anatomical_frame"]["up"]) * foot["pelvis_drop"]
    moved_arm = shifted_arm_solution(arm, shift)
    residual = apply_solution(armature, moved_arm)
    align_hand_tips(armature, moved_arm)
    return max(leg_error, *(r[k] for r in residual.values() for k in ("elbow", "wrist")))


def action_for(armature, name, samples, calibration, patches, baseline, output,
               render=False, variant="08"):
    scene = bpy.context.scene
    armature.animation_data.action = None
    root = calibration["canonical_bones"]["pelvis"]["rig_bone"]
    rotated = set()
    for sample in samples:
        rotated.update(b for leg in sample["foot"]["legs"].values()
                       for b in leg["bone_names"][:3])
        rotated.update(b for arm in sample["arm"]["arms"].values()
                       for b in arm["bone_names"])
    for index, sample in enumerate(samples, 1):
        scene.frame_set(index)
        for bone in rotated:
            armature.pose.bones[bone].rotation_mode = "QUATERNION"
        apply_both(armature, sample, calibration)
        armature.pose.bones[root].keyframe_insert(data_path="location", frame=index)
        for bone in rotated:
            armature.pose.bones[bone].keyframe_insert(data_path="rotation_quaternion", frame=index)
    action = armature.animation_data.action
    require(action is not None, f"{name}: Action missing")
    action.name, action.use_fake_user = f"MS{variant}_{name}", True
    results = []
    for index, sample in enumerate(samples, 1):
        scene.frame_set(index)
        bpy.context.view_layer.update()
        shift = -Vector(calibration["anatomical_frame"]["up"]) * sample["foot"]["pelvis_drop"]
        residual = 0.0
        for leg in sample["foot"]["legs"].values():
            for bone, target in zip(leg["bone_names"],
                                    (leg["hip"], leg["knee"], leg["ankle"], leg["ball"])):
                residual = max(residual, (armature.pose.bones[bone].head - Vector(target)).length)
            require(residual <= .005 * leg["reach"], f"{name} {index}: leg residual")
        for arm in sample["arm"]["arms"].values():
            for bone, target in zip(arm["bone_names"],
                                    (arm["shoulder"], arm["elbow"], arm["wrist"])):
                residual = max(residual, (armature.pose.bones[bone].head -
                                          Vector(target) - shift).length)
            hand_tail = armature.pose.bones[arm["bone_names"][-1]].tail
            residual = max(residual, (hand_tail - Vector(arm["hand"]) - shift).length)
            require(residual <= .005 * arm["arm_reach"], f"{name} {index}: arm residual")
        gap = measured_hand_mesh_projection(armature, calibration)["projected_gap_armature_units"]
        sole = evaluated_sole_heights(armature, patches, calibration["anatomical_frame"])
        results.append({"sample": index, "hand_gap": gap, "joint_residual": residual,
                        "lowest_sole_delta": min(sole[s]["minimum"] - baseline[s] for s in sole)})
    previews = {}
    if render:
        scene.frame_set(1 if len(samples) == 1 else (len(samples) + 1) // 2)
        previews = render_views(armature, calibration, output, prefix=name)
        if variant == "09":
            previews["feet_top"] = render_feet_top(armature, calibration, output,
                                                   name, samples[(len(samples) - 1) // 2])
    return {"action": action.name, "samples": len(samples),
            "footprint_first_sample": footprint(samples[0], calibration["anatomical_frame"]),
            "minimum_hand_gap": min(r["hand_gap"] for r in results),
            "maximum_joint_residual": max(r["joint_residual"] for r in results),
            "lowest_sole_delta_from_rest": min(r["lowest_sole_delta"] for r in results),
            "worst_hand_sample": min(results, key=lambda r: r["hand_gap"]),
            "previews": previews}


def main():
    parser = argparse.ArgumentParser()
    for key in ("repo", "calibration", "reference", "source-profile", "clearance-report",
                "en-avant-report", "first-report", "second-report", "arm-report",
                "foot-report", "output"):
        parser.add_argument(f"--{key}", type=Path, required=True)
    parser.add_argument("--turnout-degrees", type=float, default=24)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    require(args.turnout_degrees in (24, 45), "Use 24 for archived v0.8 or 45 for top-view v0.9")
    variant = "08" if args.turnout_degrees == 24 else "09"
    repo, calibration, rig, reference, reports = load_input(args)
    arm_report = json.loads(args.arm_report.read_text(encoding="utf-8"))
    foot_report = json.loads(args.foot_report.read_text(encoding="utf-8"))
    source_hash = reference["source_glb_sha256"]
    require(arm_report["status"] == "CATALOG_GEOMETRY_RENDERED" and
            not arm_report["front_overlap_names"] and
            foot_report["status"] == "CANDIDATE_GEOMETRY_RENDERED" and
            arm_report["source_glb_sha256"] == foot_report["source_glb_sha256"] == source_hash,
            "Screened arm and candidate foot reports must match this final Rig")
    lateral = arm_report["crown_selected_lateral_arm_reach_fraction"]
    overhead = arm_report["crown_selected_overhead_arm_reach_fraction"]
    arms, arm_edges, _head = build_catalog(calibration, reference, reports, lateral, overhead)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    candidates = [o for o in bpy.context.scene.objects
                  if o.type == "ARMATURE" and o.name == rig["armature"]]
    require(len(candidates) == 1, "Expected exactly one final Rig")
    armature = candidates[0]
    armature.animation_data_clear()
    armature.animation_data_create()
    frame = calibration["anatomical_frame"]
    up = Vector(frame["up"])
    bones = calibration["canonical_bones"]
    height = Vector(bones["head"]["head_local"]).dot(up) - sum(
        Vector(bones[f"{side}_foot"]["head_local"]).dot(up)
        for side in ("left", "right")) / 2
    patches = {side: select_patch(candidate_vertices(armature, calibration, side),
                                  frame, height, side)[0] for side in ("left", "right")}
    baseline = {side: min(Vector(p["position_armature_local"]).dot(up)
                          for p in patches[side]["points"]) for side in patches}
    feet = {name: guide_foot_position(calibration, patches, name,
                                     turnout_degrees=args.turnout_degrees)
            for _arm, name in PAIRS.values()}
    poses = {name: pose_sample(arms[a], feet[f]) for name, (a, f) in PAIRS.items()}
    paths = combined_paths(arms, arm_edges, feet, frame)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 49
    bpy.context.scene.render.fps = 24  # Diagnostic sampling rate, not choreography tempo.
    static = {name: action_for(armature, "pose_" + name, [sample], calibration,
                                patches, baseline, output, render=True, variant=variant)
              for name, sample in poses.items()}
    clips = {}
    for (start, end), samples in paths.items():
        for a, b, ordered, show in ((start, end, samples, True),
                                     (end, start, samples[::-1], False)):
            name = f"{a}_to_{b}"
            clips[name] = action_for(armature, name, ordered, calibration,
                                     patches, baseline, output, render=show,
                                     variant=variant)
    blend = output / f"guide_full_body_catalog_v0_{8 if variant == '08' else 9}.blend"
    armature.animation_data.action = None
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    all_items = {**static, **clips}
    overlaps = {name: v["minimum_hand_gap"] for name, v in all_items.items()
                if v["minimum_hand_gap"] < 0}
    penetration = {name: v["lowest_sole_delta_from_rest"] for name, v in all_items.items()
                   if v["lowest_sole_delta_from_rest"] < -.005 * height}
    result = {
        "status": "COMBINED_GEOMETRY_FLAGS" if overlaps or penetration else "COMBINED_CANDIDATE_RENDERED",
        "source_glb_sha256": source_hash,
        "input_arm_status": arm_report["status"], "input_foot_status": foot_report["status"],
        "selected_crown_lateral_fraction": lateral,
        "selected_crown_overhead_fraction": overhead,
        "turnout_candidate_degrees_per_foot": args.turnout_degrees,
        "poses": static, "clips": clips,
        "pair_routes": {f"{a}_to_{b}": route_arm_positions(a, b, paths)
                        for a in poses for b in poses if a != b},
        "hand_overlap_names": overlaps, "sole_penetration_names": penetration,
        "blend": str(blend),
        "limits": "Coupled arm and leg candidates on one Rig; no measured timing, floor contact/friction, "
                  "turnout standard, balance, full mesh or hair collision, teacher review, or Godot export."}
    path = output / "report.json"
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"MOTION_STUDIO_FULL_BODY={result['status']}")
    print(f"REPORT={path}")
    print(f"BLEND={blend}")


if __name__ == "__main__":
    main()
