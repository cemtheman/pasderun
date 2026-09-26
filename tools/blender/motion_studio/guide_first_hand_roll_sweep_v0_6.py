"""Symmetric hand-roll sweep for the provisional guide first-position waypoint.

Keeps shoulder/elbow/wrist targets fixed and varies only final-Rig hand-bone
roll about the forearm axis. This is a visual candidate sweep, not ballet
approval and not a change to accepted Phase 10 assets.
"""

from __future__ import annotations

import argparse
import json
import sys
from math import radians
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
from hand_clearance_candidate import shifted_solution  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose import dot  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


DEFAULT_ROLL_DEGREES = (-30.0, -20.0, -10.0, 0.0, 10.0, 20.0, 30.0)


def rotate_hand_about_forearm(armature, solution, side, degrees):
    arm = solution["arms"][side]
    lower_name, hand_name = arm["bone_names"][1], arm["bone_names"][2]
    lower = armature.pose.bones[lower_name]
    hand = armature.pose.bones[hand_name]
    bpy.context.view_layer.update()

    wrist = hand.head.copy()
    elbow = lower.head.copy()
    axis = wrist - elbow
    require(axis.length > 1e-8, f"{side}: degenerate forearm axis")
    axis.normalize()

    rotation = Matrix.Rotation(radians(degrees), 4, axis)
    hand.matrix = (
        Matrix.Translation(wrist)
        @ rotation
        @ Matrix.Translation(-wrist)
        @ hand.matrix.copy()
    )
    bpy.context.view_layer.update()


def hand_direction_metrics(armature, solution, calibration):
    left_axis = Vector(calibration["anatomical_frame"]["left"]).normalized()
    up_axis = Vector(calibration["anatomical_frame"]["up"]).normalized()
    front_axis = Vector(calibration["anatomical_frame"]["front"]).normalized()
    result = {}

    for side in ("left", "right"):
        hand_name = solution["arms"][side]["bone_names"][2]
        hand = armature.pose.bones[hand_name]
        direction = (hand.tail - hand.head).normalized()
        inward_axis = -left_axis if side == "left" else left_axis
        result[side] = {
            "tail_direction_armature": [round(v, 8) for v in direction],
            "inward_component": round(direction.dot(inward_axis), 8),
            "up_component": round(direction.dot(up_axis), 8),
            "front_component": round(direction.dot(front_axis), 8),
        }
    return result


def main():
    parser = argparse.ArgumentParser()
    for name in (
        "repo",
        "calibration",
        "reference",
        "source-profile",
        "clearance-report",
        "en-avant-report",
        "output",
    ):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument(
        "--roll-degrees",
        nargs="*",
        type=float,
        default=list(DEFAULT_ROLL_DEGREES),
        help="Symmetric hand roll in degrees: left receives +angle, right receives -angle.",
    )
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

    repo, output = args.repo.resolve(), args.output.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    rig = json.loads(
        (repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(
            encoding="utf-8"
        )
    )
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    require(
        reference
        == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
        "Reference differs from exact accepted Phase 10 source",
    )

    clearance = json.loads(args.clearance_report.read_text(encoding="utf-8"))
    en_avant = json.loads(args.en_avant_report.read_text(encoding="utf-8"))
    for name, report in (("clearance", clearance), ("en_avant", en_avant)):
        require(
            report.get("source_profile_sha256") == reference["source_profile_sha256"]
            and report.get("source_glb_sha256") == reference["source_glb_sha256"],
            f"{name}: source digest mismatch",
        )

    anatomical_frame = calibration["anatomical_frame"]
    low = shifted_solution(
        joint_targets(reference, calibration, "bras_bas"),
        anatomical_frame,
        clearance["poses"]["bras_bas"]["outward_shift_per_wrist_armature_units"],
    )
    high = shifted_solution(
        joint_targets(reference, calibration, "en_avant"),
        anatomical_frame,
        en_avant["outward_shift_per_wrist_armature_units"],
        "body_outward",
    )
    spine_mid_height = dot(
        calibration["canonical_bones"]["spine_mid"]["head_local"],
        anatomical_frame["up"],
    )
    candidate = guide_first_position(
        low,
        high,
        anatomical_frame,
        navel_region_height=spine_mid_height,
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "ARMATURE" and obj.name == rig["armature"]
    ]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    bpy.context.scene.frame_set(1)
    output.mkdir(parents=True, exist_ok=True)

    results = []
    for angle in args.roll_degrees:
        for bone in armature.pose.bones:
            bone.matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()

        residuals = apply_solution(armature, candidate)
        baseline_hand_tip_residuals = align_hand_tips(armature, candidate)

        rotate_hand_about_forearm(armature, candidate, "left", angle)
        rotate_hand_about_forearm(armature, candidate, "right", -angle)

        projection = measured_hand_mesh_projection(armature, calibration)
        metrics = hand_direction_metrics(armature, candidate, calibration)

        tag = f"{angle:+.0f}".replace("+", "p").replace("-", "m")
        previews = render_views(
            armature,
            calibration,
            output,
            prefix=f"guide_first_hand_roll_{tag}",
        )
        results.append(
            {
                "symmetric_roll_degrees": angle,
                "left_applied_degrees": angle,
                "right_applied_degrees": -angle,
                "arm_residuals_before_hand_roll": residuals,
                "baseline_hand_tip_residuals_before_hand_roll": baseline_hand_tip_residuals,
                "hand_direction": metrics,
                "hand_mesh_projection": projection,
                "previews": previews,
            }
        )

    blend = output / "guide_first_hand_roll_sweep_v0_6.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {
        "status": "FIRST_POSITION_HAND_ROLL_SWEEP_VISUAL_REVIEW_REQUIRED",
        "source_profile_sha256": reference["source_profile_sha256"],
        "source_glb_sha256": reference["source_glb_sha256"],
        "guide_pdf_sha256": "2d6321bf92dd97014fb86555bc30426772e9a34e0527e7bf397339fa3648793d",
        "fixed_geometry": {
            "wrist_height_method": "calibrated spine_mid head elevation torso proxy",
            "shoulder_elbow_wrist_targets_unchanged": True,
            "feet_unchanged": True,
        },
        "roll_convention": (
            "Positive sweep angle rotates the left hand +angle and right hand -angle "
            "about each forearm axis. Negative values test the opposite mirrored roll."
        ),
        "candidates": results,
        "blend": str(blend),
        "limits": (
            "Visual hand-orientation sweep only. No measured palm normal, finger articulation, "
            "3D collision proof, physiological wrist limit, motion timing or ballet-teacher approval. "
            "Choose a visual candidate before authoring any path."
        ),
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("MOTION_STUDIO_FIRST_HAND_ROLL=SWEEP_VISUAL_REVIEW_REQUIRED")
    print(f"REPORT={report_path}")
    for item in results:
        print(
            "ROLL="
            f"{item['symmetric_roll_degrees']:+.0f} "
            f"GAP={item['hand_mesh_projection']['projected_gap_armature_units']}"
        )
        print(f"FRONT={item['previews']['front']}")
        print(f"SIDE={item['previews']['side']}")
    print(f"BLEND={blend}")


if __name__ == "__main__":
    main()
