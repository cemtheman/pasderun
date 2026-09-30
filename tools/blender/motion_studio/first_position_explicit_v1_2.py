"""Explicit First Position scaffold v1.2.

Goal:
- lower the hands from v0.8
- move the oval slightly forward from the torso
- keep elbows softly open to the sides
- avoid the waist-level / sharp-elbow silhouette

Static visual review only.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy

MOTION_TOOLS = Path(__file__).resolve().parents[2] / "motion_studio"
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(MOTION_TOOLS))
sys.path.insert(0, str(HERE))

from accepted_arm_reference import extract_accepted_arm_reference  # noqa: E402
from accepted_arm_visual import joint_targets  # noqa: E402
from accepted_arm_visual_v0_6 import measured_hand_mesh_projection  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose import add, dot, mul, sub, unit/  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402
from first_position_finger_aware_v0_7 import (  # noqa: E402
    align_hand_to_forearm,
    reset_pose,
    shape_ballet_hand,
)

CANDIDATES = {
    # v1.2 stops using a wrist goal + bend pole.  Each arm segment is authored
    # directly in body-relative directions, so the elbow height/silhouette is
    # controlled explicitly instead of emerging indirectly from the IK circle.
    "oval_low": {
        "upper_out": 0.92,
        "upper_down": 0.30,
        "upper_front": 0.12,
        "lower_in": 0.82,
        "lower_down": 0.50,
        "lower_front": 0.34,
    },
    "oval_classical": {
        "upper_out": 0.94,
        "upper_down": 0.27,
        "upper_front": 0.12,
        "lower_in": 0.84,
        "lower_down": 0.46,
        "lower_front": 0.34,
    },
    "oval_lifted": {
        "upper_out": 0.96,
        "upper_down": 0.24,
        "upper_front": 0.10,
        "lower_in": 0.86,
        "lower_down": 0.42,
        "lower_front": 0.32,
    },
}

FINGER_STRENGTH = 1.0


def standing_height(calibration: dict) -> float:
    frame = calibration["anatomical_frame"]
    up = frame["up"]
    bones = calibration["canonical_bones"]
    head = bones["head"]["head_local"]
    feet = [bones[f"{side}_foot"]["head_local"] for side in ("left", "right")]
    h = dot(head, up) - sum(dot(foot, up) for foot in feet) / 2.0
    require(h > 0.0, "Degenerate standing height")
    return h


def point_from_body_offsets(origin, frame, left_value, up_value, front_value):
    return add(
        origin,
        add(
            mul(frame["left"], left_value),
            add(mul(frame["up"], up_value), mul(frame["front"], front_value)),
        ),
    )


def explicit_first_position(reference, calibration, params):
    frame = calibration["anatomical_frame"]
    base = joint_targets(reference, calibration, "en_avant")

    result = {}
    for side in ("left", "right"):
        source = base["arms"][side]
        outward = frame["left"] if side == "left" else mul(frame["left"], -1.0)
        inward = mul(outward, -1.0)

        upper_length = math.dist(source["shoulder"], source["elbow"])
        lower_length = math.dist(source["elbow"], source["wrist"])

        upper_dir = unit(
            add(
                mul(outward, params["upper_out"]),
                add(
                    mul(frame["up"], -params["upper_down"]),
                    mul(frame["front"], params["upper_front"]),
                ),
            ),
            f"{side}_first_v1_2_upper",
        )
        elbow = add(source["shoulder"], mul(upper_dir, upper_length))

        lower_dir = unit(
            add(
                mul(inward, params["lower_in"]),
                add(
                    mul(frame["up"], -params["lower_down"]),
                    mul(frame["front"], params["lower_front"]),
                ),
            ),
            f"{side}_first_v1_2_lower",
        )
        wrist = add(elbow, mul(lower_dir, lower_length))

        hand = add(wrist, sub(source["hand"], source["wrist"]))
        result[side] = {
            **source,
            "elbow": elbow,
            "wrist": wrist,
            "hand": hand,
        }

    return {
        "pose_id": "first_position_explicit_v1_2",
        "arms": result,
    }

def body_axis_value(point, axis):
    return dot(point, axis)


def scaffold_metrics(solution, calibration):
    frame = calibration["anatomical_frame"]
    up, left, front = frame["up"], frame["left"], frame["front"]
    metrics = {}
    for side in ("left", "right"):
        arm = solution["arms"][side]
        sign = 1.0 if side == "left" else -1.0
        shoulder_up = body_axis_value(arm["shoulder"], up)
        elbow_up = body_axis_value(arm["elbow"], up)
        wrist_up = body_axis_value(arm["wrist"], up)
        metrics[side] = {
            "shoulder_up": round(shoulder_up, 8),
            "elbow_up": round(elbow_up, 8),
            "wrist_up": round(wrist_up, 8),
            "elbow_above_wrist": elbow_up > wrist_up,
            "elbow_below_shoulder": elbow_up < shoulder_up,
            "elbow_lateral": round(sign * body_axis_value(arm["elbow"], left), 8),
            "wrist_lateral": round(sign * body_axis_value(arm["wrist"], left), 8),
            "wrist_front": round(body_axis_value(arm["wrist"], front), 8),
        }
    return metrics


def pose_candidate(armature, calibration, mapping, reference, params):
    reset_pose(armature)
    solution = explicit_first_position(reference, calibration, params)
    residuals = apply_solution(armature, solution)

    continuity = {}
    hand_shapes = {}
    for side in ("left", "right"):
        continuity[side] = align_hand_to_forearm(armature, solution, side)
        hand_shapes[side] = shape_ballet_hand(
            armature, mapping, calibration, solution, side, FINGER_STRENGTH
        )

    projection = measured_hand_mesh_projection(armature, calibration)
    return solution, residuals, continuity, hand_shapes, projection


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
    require(
        reference == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
        "Reference differs from regenerated accepted Phase 10 source",
    )
    require(
        mapping.get("source_glb_sha256") == reference["source_glb_sha256"],
        "Finger mapping source SHA does not match regenerated reference",
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [
        obj for obj in bpy.context.scene.objects
        if obj.type == "ARMATURE" and obj.name == rig["armature"]
    ]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    bpy.context.scene.frame_set(1)

    results = {}
    for label, params in CANDIDATES.items():
        solution, residuals, continuity, hand_shapes, projection = pose_candidate(
            armature, calibration, mapping, reference, params
        )
        previews = render_views(
            armature, calibration, output, prefix=f"first_v1_2_{label}"
        )
        results[label] = {
            "parameters": params,
            "residuals": residuals,
            "hand_continuity_deg": continuity,
            "scaffold_metrics": scaffold_metrics(solution, calibration),
            "hand_shape": hand_shapes,
            "hand_mesh_projection": projection,
            "previews": previews,
        }

    blend = output / "first_position_explicit_v1_2.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))

    report = {
        "status": "FIRST_POSITION_EXPLICIT_V1_2_VISUAL_REVIEW_REQUIRED",
        "source_glb_sha256": reference["source_glb_sha256"],
        "source_profile_sha256": reference["source_profile_sha256"],
        "finger_mapping_profile_id": mapping["profile_id"],
        "finger_strength": FINGER_STRENGTH,
        "scaffold_policy": (
            "Direct body-relative upper-arm and forearm segment directions; explicit elbow arc, no wrist-goal bend-pole solve; "
            "no bras-bas/en-avant interpolation."
        ),
        "candidates": results,
        "blend": str(blend),
        "limits": (
            "Static visual candidate sweep only. No animation, teacher approval, "
            "scapula solve, physiological joint-limit proof, or temporal smoothing."
        ),
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("MOTION_STUDIO_FIRST_POSITION_V1_2=VISUAL_REVIEW_REQUIRED")
    print(f"SOURCE_SHA256={reference['source_glb_sha256']}")
    print(f"REPORT={report_path}")
    for label, item in results.items():
        m = item["scaffold_metrics"]["left"]
        print(
            f"{label.upper()} "
            f"ELBOW_UP={m['elbow_up']:.8f} "
            f"WRIST_UP={m['wrist_up']:.8f} "
            f"WRIST_LAT={m['wrist_lateral']:.8f} "
            f"WRIST_FRONT={m['wrist_front']:.8f} "
            f"GAP={item['hand_mesh_projection']['projected_gap_armature_units']:.8f}"
        )
        print(f"{label.upper()}_FRONT={item['previews']['front']}")
        print(f"{label.upper()}_SIDE={item['previews']['side']}")
    print(f"BLEND={blend}")


if __name__ == "__main__":
    main()
