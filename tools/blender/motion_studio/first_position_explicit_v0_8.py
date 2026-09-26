"""Explicit First Position scaffold v0.8 on the repaired canonical rig.

v0.7 proved the finger rig and skinning are clean, but its arm scaffold was
derived from bras-bas + shifted en-avant and read visually as hands near the
waist with overly acute elbows. v0.8 stops interpolating those inherited poses.

Instead it authors a small, explicit family of First Position wrist targets in
body-relative coordinates, solves the two-link arm directly, and uses an
outward+upward elbow pole so the arm forms a supported rounded oval in front of
the torso. Finger shaping is reused unchanged from the validated v0.7 path.

Static visual review only; no animation and no teacher-approval claim.
"""

from __future__ import annotations

import argparse
import json
import math
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
from accepted_arm_visual_v0_6 import measured_hand_mesh_projection  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose import add, dot, mul, solve_two_link, sub  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402
from first_position_finger_aware_v0_7 import (  # noqa: E402
    align_hand_to_forearm,
    reset_pose,
    shape_ballet_hand,
)


CANDIDATES = {
    # lateral/up/front are standing-height fractions from pelvis origin.
    # elbow_up biases the bend pole upward while preserving lateral openness.
    "compact": {
        "wrist_lateral": 0.078,
        "wrist_up": 0.238,
        "wrist_front": 0.180,
        "elbow_up": 0.58,
        "elbow_front": 0.08,
    },
    "classical": {
        "wrist_lateral": 0.086,
        "wrist_up": 0.248,
        "wrist_front": 0.185,
        "elbow_up": 0.48,
        "elbow_front": 0.08,
    },
    "lifted": {
        "wrist_lateral": 0.094,
        "wrist_up": 0.258,
        "wrist_front": 0.180,
        "elbow_up": 0.38,
        "elbow_front": 0.06,
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
    origin = calibration["canonical_bones"]["pelvis"]["head_local"]
    height = standing_height(calibration)

    result = {}
    for side in ("left", "right"):
        source = base["arms"][side]
        sign = 1.0 if side == "left" else -1.0

        wrist = point_from_body_offsets(
            origin,
            frame,
            sign * height * params["wrist_lateral"],
            height * params["wrist_up"],
            height * params["wrist_front"],
        )

        outward = frame["left"] if side == "left" else mul(frame["left"], -1.0)
        pole = add(
            outward,
            add(
                mul(frame["up"], params["elbow_up"]),
                mul(frame["front"], params["elbow_front"]),
            ),
        )

        solved = solve_two_link(
            source["shoulder"],
            source["elbow"],
            source["wrist"],
            wrist,
            pole,
            f"{side}_first_v0_8",
        )

        # Hand endpoint is metadata only for this scaffold; actual Hand bone is
        # aligned after arm solve to continue the forearm without a wrist kink.
        hand = add(wrist, sub(source["hand"], source["wrist"]))
        arm = {
            **source,
            "elbow": solved["elbow"],
            "wrist": wrist,
            "hand": hand,
        }
        result[side] = arm

    return {
        "pose_id": "first_position_explicit_v0_8",
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
            armature, calibration, output, prefix=f"first_v0_8_{label}"
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

    blend = output / "first_position_explicit_v0_8.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))

    report = {
        "status": "FIRST_POSITION_EXPLICIT_V0_8_VISUAL_REVIEW_REQUIRED",
        "source_glb_sha256": reference["source_glb_sha256"],
        "source_profile_sha256": reference["source_profile_sha256"],
        "finger_mapping_profile_id": mapping["profile_id"],
        "finger_strength": FINGER_STRENGTH,
        "scaffold_policy": (
            "Explicit body-relative First Position wrist targets; two-link solve "
            "with outward+upward elbow pole. No bras-bas/en-avant interpolation."
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

    print("MOTION_STUDIO_FIRST_POSITION_V0_8=VISUAL_REVIEW_REQUIRED")
    print(f"SOURCE_SHA256={reference['source_glb_sha256']}")
    print(f"REPORT={report_path}")
    for label, item in results.items():
        l = item["scaffold_metrics"]["left"]
        print(
            f"{label.upper()} "
            f"ELBOW_UP={l['elbow_up']:.8f} "
            f"WRIST_UP={l['wrist_up']:.8f} "
            f"WRIST_LAT={l['wrist_lateral']:.8f} "
            f"GAP={item['hand_mesh_projection']['projected_gap_armature_units']:.8f}"
        )
        print(f"{label.upper()}_FRONT={item['previews']['front']}")
        print(f"{label.upper()}_SIDE={item['previews']['side']}")
    print(f"BLEND={blend}")


if __name__ == "__main__":
    main()
