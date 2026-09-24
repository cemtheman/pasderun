"""Generate provisional five-position footwork on the calibrated final Rig."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

TOOLS = Path(__file__).resolve().parents[2] / "motion_studio"
sys.path.insert(0, str(TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from guide_arm_catalog import route_arm_positions  # noqa: E402
from guide_foot_catalog import FOOT_POSITIONS, guide_foot_position, sample_foot_transition  # noqa: E402
from rest_foot_contact_v0_4 import candidate_vertices, select_patch  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose_preview_v0_3 import align_joint, render_views, require  # noqa: E402


def reset_pose(armature):
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def apply_feet(armature, sample, calibration):
    frame = calibration["anatomical_frame"]
    root_name = calibration["canonical_bones"]["pelvis"]["rig_bone"]
    root = armature.pose.bones[root_name]
    require(root.parent is None, "Pelvis must be the Rig root for common plié")
    translation = -Vector(frame["up"]) * sample["pelvis_drop"]
    root.matrix = Matrix.Translation(translation) @ root.matrix.copy()
    bpy.context.view_layer.update()
    maximum_error = 0.0
    for side, leg in sample["legs"].items():
        upper, lower, foot, toes = leg["bone_names"]
        for name in (upper, lower, foot, toes):
            require(name in armature.pose.bones, f"{side}: Rig bone {name} absent")
        hip, knee, ankle, ball = (Vector(leg[key]) for key in ("hip", "knee", "ankle", "ball"))
        maximum_error = max(maximum_error, (armature.pose.bones[upper].head - hip).length)
        align_joint(armature, upper, lower, knee - hip)
        align_joint(armature, lower, foot, ankle - knee)
        align_joint(armature, foot, toes, ball - ankle)
        for name, target in ((lower, knee), (foot, ankle), (toes, ball)):
            maximum_error = max(maximum_error, (armature.pose.bones[name].head - target).length)
        require(maximum_error <= leg["reach"] * .005,
                f"{sample['pose_id']} {side}: joint residual {maximum_error:.7f}")
    return maximum_error


def evaluated_sole_heights(armature, patches, frame):
    """Track original sole outline vertex IDs through the evaluated skin mesh."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    values = {}
    local = armature.matrix_world.inverted()
    for side, patch in patches.items():
        heights = []
        for point in patch["points"]:
            obj_name, marker, index = point["reference"].rpartition(":vertex:")
            require(bool(obj_name) and bool(marker), "Sole reference missing vertex index")
            obj = bpy.data.objects[obj_name]
            evaluated = obj.evaluated_get(depsgraph)
            mesh = evaluated.to_mesh()
            try:
                require(int(index) < len(mesh.vertices), "Evaluated mesh topology changed")
                local_position = local @ evaluated.matrix_world @ mesh.vertices[int(index)].co
                heights.append(local_position.dot(Vector(frame["up"])))
            finally:
                evaluated.to_mesh_clear()
        require(heights, f"{side}: no evaluated sole vertices")
        values[side] = {"minimum": min(heights), "maximum": max(heights),
                        "spread": max(heights) - min(heights)}
    return values


def make_action(armature, name, samples, calibration, patches, baseline, output, render=False):
    scene = bpy.context.scene
    armature.animation_data.action = None
    root_name = calibration["canonical_bones"]["pelvis"]["rig_bone"]
    keyed_names = {root_name}
    for sample in samples:
        for leg in sample["legs"].values():
            keyed_names.update(leg["bone_names"][:3])
    for frame_number, sample in enumerate(samples, 1):
        scene.frame_set(frame_number)
        reset_pose(armature)
        for bone_name in keyed_names:
            armature.pose.bones[bone_name].rotation_mode = "QUATERNION"
        apply_feet(armature, sample, calibration)
        armature.pose.bones[root_name].keyframe_insert(data_path="location", frame=frame_number)
        for bone_name in keyed_names - {root_name}:
            armature.pose.bones[bone_name].keyframe_insert(
                data_path="rotation_quaternion", frame=frame_number)
    action = armature.animation_data.action
    require(action is not None, f"{name}: no keyed Action")
    action.name, action.use_fake_user = f"MS07_FOOT_{name}", True
    checked = []
    for frame_number, sample in enumerate(samples, 1):
        scene.frame_set(frame_number)
        bpy.context.view_layer.update()
        error = 0.0
        for leg in sample["legs"].values():
            for bone_name, target in zip(leg["bone_names"],
                                         (leg["hip"], leg["knee"], leg["ankle"], leg["ball"])):
                error = max(error, (armature.pose.bones[bone_name].head - Vector(target)).length)
            require(error <= leg["reach"] * .005,
                    f"{name} frame {frame_number}: keyed playback residual {error:.7f}")
        heights = evaluated_sole_heights(armature, patches, calibration["anatomical_frame"])
        checked.append({"sample": frame_number, "joint_residual": round(error, 8),
                        "sole": {side: {"minimum_delta_from_rest": round(v["minimum"] - baseline[side], 7),
                                        "spread": round(v["spread"], 7)}
                                 for side, v in heights.items()}})
    previews = {}
    if render:
        scene.frame_set(1 if len(samples) == 1 else (len(samples) + 1) // 2)
        previews = render_views(armature, calibration, output, prefix=name)
    return {"action": action.name, "samples": len(samples),
            "maximum_joint_residual": max(row["joint_residual"] for row in checked),
            "lowest_sole_delta_from_rest": min(v["minimum_delta_from_rest"]
                                               for row in checked for v in row["sole"].values()),
            "highest_sole_delta_from_rest": max(v["minimum_delta_from_rest"]
                                                for row in checked for v in row["sole"].values()),
            "worst_contact_sample": min(checked, key=lambda row: min(
                v["minimum_delta_from_rest"] for v in row["sole"].values())),
            "previews": previews}


def main():
    parser = argparse.ArgumentParser()
    for field in ("repo", "calibration", "output"):
        parser.add_argument(f"--{field}", required=True, type=Path)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])
    repo = args.repo.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects
                 if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one calibrated final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    armature.animation_data_create()
    frame = calibration["anatomical_frame"]
    bones = calibration["canonical_bones"]
    height = Vector(bones["head"]["head_local"]).dot(Vector(frame["up"])) - sum(
        Vector(bones[f"{side}_foot"]["head_local"]).dot(Vector(frame["up"]))
        for side in ("left", "right")) / 2
    patches, extraction = {}, {}
    for side in ("left", "right"):
        patches[side], extraction[side] = select_patch(
            candidate_vertices(armature, calibration, side), frame, height, side)
    baseline = {side: min(Vector(p["position_armature_local"]).dot(Vector(frame["up"]))
                          for p in patch["points"]) for side, patch in patches.items()}
    poses = {name: guide_foot_position(calibration, patches, name) for name in FOOT_POSITIONS}
    edges = {(name, "first"): [] for name in FOOT_POSITIONS[1:]}
    samples = {(a, b): sample_foot_transition(poses[b], poses[a], frame)
               for a, b in edges}
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.frame_start, bpy.context.scene.frame_end = 1, 25
    bpy.context.scene.render.fps = 24
    static_report = {name: make_action(armature, "pose_" + name, [pose],
                                       calibration, patches, baseline, output, render=True)
                     for name, pose in poses.items()}
    clips = {}
    for (end, start), path in samples.items():
        clips[f"{start}_to_{end}"] = make_action(
            armature, f"{start}_to_{end}", path, calibration, patches, baseline, output, render=True)
        clips[f"{end}_to_{start}"] = make_action(
            armature, f"{end}_to_{start}", path[::-1], calibration, patches, baseline, output)
    blend = output / "guide_foot_catalog_v0_7.blend"
    armature.animation_data.action = None
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    # The baseline is the observed rest sole, not a claimed physical floor.
    below = {name: value["lowest_sole_delta_from_rest"] for name, value in
             {**static_report, **clips}.items() if value["lowest_sole_delta_from_rest"] < -.005 * height}
    report = {"status": "CANDIDATE_SOLE_PENETRATION" if below else "CANDIDATE_GEOMETRY_RENDERED",
              "source_glb_sha256": calibration["source"]["sha256"],
              "guide_pdf_sha256": "2d6321bf92dd97014fb86555bc30426772e9a34e0527e7bf397339fa3648793d",
              "sole_extraction": extraction, "rest_sole_minimum_up": baseline,
              "poses": static_report, "clips": clips, "sole_penetration_names": below,
              "pair_routes": {f"{a}_to_{b}": route_arm_positions(a, b, edges)
                              for a in poses for b in poses if a != b},
              "blend": str(blend),
              "limits": "Eight provisional lower-body targets, fourteen reversible actions; arms are at rest. "
                        "Projected rest sole is an approximation, not a measured floor or complete contact patch. "
                        "No slip, self-collision, balance, anatomical turnout, teacher approval or timed choreography verified."}
    path = output / "report.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"MOTION_STUDIO_GUIDE_FOOT_CATALOG={report['status']}")
    print(f"REPORT={path}")
    print(f"BLEND={blend}")


if __name__ == "__main__":
    main()
