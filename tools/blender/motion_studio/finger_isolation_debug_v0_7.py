"""Isolate each finger-chain deformation on the repaired final Rig.

This diagnostic exists because the first finger-aware First Position render
showed a large skinned-mesh spike although reported fingertip coordinates were
locally plausible. The test keeps one arm/hand scaffold fixed, shapes exactly
one finger chain at a time, renders front/side, and measures evaluated mesh
AABB/vertex displacement against the same scaffold with no finger shaping.

It does not alter source assets or claim ballet acceptance.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector

MOTION_TOOLS = Path(__file__).resolve().parents[2] / "motion_studio"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTION_TOOLS))
sys.path.insert(0, str(HERE))

from accepted_arm_reference import extract_accepted_arm_reference  # noqa: E402
from accepted_arm_visual import joint_targets  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402
from ring_weight_sanitizer_v0_1 import sanitize_ring_weights  # noqa: E402
from first_position_finger_aware_v0_7 import (  # noqa: E402
    SHAPE_LEVELS,
    align_hand_to_forearm,
    blend_dir,
    build_first_scaffold,
    normalized,
    shape_finger_chain,
)


FINGERS = ("thumb", "index", "middle", "ring", "pinky")


def reset_pose(armature):
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def evaluated_mesh_points(armature):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    rig_inverse = armature.matrix_world.inverted()
    objects = {}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        if not any(mod.type == "ARMATURE" and mod.object == armature for mod in obj.modifiers):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            to_local = rig_inverse @ evaluated.matrix_world
            points = [to_local @ v.co for v in mesh.vertices]
            if points:
                objects[obj.name] = points
        finally:
            evaluated.to_mesh_clear()
    return objects


def aabb(points):
    xs = [p.x for p in points]
    ys = [p.y for p in points]
    zs = [p.z for p in points]
    return {
        "min": [min(xs), min(ys), min(zs)],
        "max": [max(xs), max(ys), max(zs)],
    }


def diag(box):
    mn, mx = box["min"], box["max"]
    return ((mx[0]-mn[0])**2 + (mx[1]-mn[1])**2 + (mx[2]-mn[2])**2) ** 0.5


def compare_meshes(baseline, current):
    report = {}
    max_displacement = 0.0
    max_object = None
    for name, base_points in baseline.items():
        pts = current.get(name)
        if pts is None or len(pts) != len(base_points):
            continue
        displacements = [(a-b).length for a, b in zip(pts, base_points)]
        obj_max = max(displacements, default=0.0)
        base_box = aabb(base_points)
        cur_box = aabb(pts)
        base_diag = diag(base_box)
        cur_diag = diag(cur_box)
        ratio = cur_diag / max(base_diag, 1e-8)
        report[name] = {
            "vertex_count": len(pts),
            "max_vertex_displacement": round(obj_max, 8),
            "baseline_aabb_diag": round(base_diag, 8),
            "current_aabb_diag": round(cur_diag, 8),
            "aabb_diag_ratio": round(ratio, 8),
        }
        if obj_max > max_displacement:
            max_displacement = obj_max
            max_object = name
    return {
        "objects": report,
        "max_vertex_displacement": round(max_displacement, 8),
        "max_displacement_object": max_object,
    }


def scaffold_pose(armature, calibration, reference):
    # Use the first feasible en-avant-derived lateral scaffold only. Do not run
    # the hand-clearance search here; this test diagnoses deformation, not pose.
    from first_position_finger_aware_v0_7 import minimum_feasible_en_avant_shift
    shift, steps = minimum_feasible_en_avant_shift(reference, calibration)
    reset_pose(armature)
    candidate = build_first_scaffold(reference, calibration, shift)
    residuals = apply_solution(armature, candidate)
    continuity = {}
    for side in ("left", "right"):
        continuity[side] = align_hand_to_forearm(armature, candidate, side)
    bpy.context.view_layer.update()
    return candidate, shift, steps, residuals, continuity


def target_for_finger(armature, mapping, calibration, candidate, side, finger, strength):
    frame = calibration["anatomical_frame"]
    up = Vector(frame["up"])
    front = Vector(frame["front"])
    left = Vector(frame["left"])
    inward = -left if side == "left" else left
    hand_name = mapping["hands"][side]["hand"]
    hand = armature.pose.bones[hand_name]
    hand_forward = normalized(hand.tail - hand.head)
    curl_axis = normalized(front + up * -0.20)

    if finger == "index":
        target = blend_dir(hand_forward, (up, +0.055 * strength), (inward, +0.025 * strength))
        bends = (0.035 * strength, 0.025 * strength)
    elif finger == "middle":
        target = blend_dir(hand_forward, (up, -0.020 * strength), (inward, +0.065 * strength))
        bends = (0.055 * strength, 0.040 * strength)
    elif finger == "ring":
        target = blend_dir(hand_forward, (up, -0.050 * strength), (inward, +0.050 * strength))
        bends = (0.065 * strength, 0.050 * strength)
    elif finger == "pinky":
        target = blend_dir(hand_forward, (up, -0.080 * strength), (inward, +0.025 * strength))
        bends = (0.075 * strength, 0.060 * strength)
    else:
        thumb_chain = mapping["hands"][side]["thumb"]
        middle_chain = mapping["hands"][side]["middle"]
        thumb = armature.pose.bones[thumb_chain[0]]
        middle_joint = armature.pose.bones[middle_chain[1]].head.copy()
        thumb_to_middle = normalized(middle_joint - thumb.head)
        target = normalized(
            hand_forward * (1.0 - 0.42 * strength)
            + thumb_to_middle * (0.42 * strength)
        )
        bends = (0.070 * strength, 0.050 * strength)
    return target, curl_axis, bends


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "calibration", "reference", "source-profile", "mapping", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

    repo = args.repo.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)
    require(reference == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
            "Reference differs from regenerated accepted source")
    require(mapping["source_glb_sha256"] == reference["source_glb_sha256"],
            "Finger mapping source SHA mismatch")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [o for o in bpy.context.scene.objects if o.type == "ARMATURE" and o.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    bpy.context.scene.frame_set(1)

    ring_weight_sanitization = sanitize_ring_weights(armature, mapping)
    print(f"RING_WEIGHT_SANITIZER_REMOVED={ring_weight_sanitization['removed_total']}")

    candidate, shift, steps, residuals, continuity = scaffold_pose(
        armature, calibration, reference
    )
    baseline_points = evaluated_mesh_points(armature)
    baseline_views = render_views(armature, calibration, output, prefix="baseline_no_fingers")

    results = {}
    strength = SHAPE_LEVELS["balanced"]
    for side in ("left", "right"):
        for finger in FINGERS:
            candidate, _, _, _, _ = scaffold_pose(armature, calibration, reference)
            chain = mapping["hands"][side][finger]
            target, curl_axis, bends = target_for_finger(
                armature, mapping, calibration, candidate, side, finger, strength
            )
            shape_finger_chain(armature, chain, target, curl_axis, bends[0], bends[1])
            bpy.context.view_layer.update()
            points = evaluated_mesh_points(armature)
            deformation = compare_meshes(baseline_points, points)
            previews = render_views(
                armature, calibration, output, prefix=f"{side}_{finger}_only"
            )
            tip = armature.pose.bones[chain[-1]].tail.copy()
            key = f"{side}_{finger}"
            results[key] = {
                "side": side,
                "finger": finger,
                "chain": chain,
                "tip_armature": [round(float(v), 8) for v in tip],
                "deformation": deformation,
                "previews": previews,
            }

    ranked = sorted(
        (
            (key, value["deformation"]["max_vertex_displacement"],
             max((o["aabb_diag_ratio"] for o in value["deformation"]["objects"].values()), default=1.0))
            for key, value in results.items()
        ),
        key=lambda item: (item[1], item[2]),
        reverse=True,
    )
    suspects = [
        {"candidate": key, "max_vertex_displacement": disp, "max_aabb_diag_ratio": ratio}
        for key, disp, ratio in ranked[:4]
    ]

    report = {
        "status": "FINGER_ISOLATION_DIAGNOSTIC_COMPLETE",
        "source_glb_sha256": reference["source_glb_sha256"],
        "scaffold": {
            "initial_shift": round(shift, 8),
            "feasibility_steps": steps,
            "arm_residuals": residuals,
            "hand_continuity_deg": continuity,
        },
        "ring_weight_sanitization": ring_weight_sanitization,
        "baseline_previews": baseline_views,
        "results": results,
        "suspects": suspects,
        "limits": (
            "Diagnostic only. Ranking is based on evaluated-mesh displacement/AABB expansion "
            "relative to the same First Position scaffold with no finger shaping. It does not "
            "identify ballet correctness by itself."
        ),
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("MOTION_STUDIO_FINGER_ISOLATION=COMPLETE")
    print(f"SOURCE_SHA256={reference['source_glb_sha256']}")
    print(f"REPORT={report_path}")
    for suspect in suspects:
        print(
            "SUSPECT="
            f"{suspect['candidate']} "
            f"MAX_DISP={suspect['max_vertex_displacement']:.8f} "
            f"AABB_RATIO={suspect['max_aabb_diag_ratio']:.8f}"
        )


if __name__ == "__main__":
    main()
