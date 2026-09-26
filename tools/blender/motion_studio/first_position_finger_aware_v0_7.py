"""Finger-aware First Position static ballet-hand candidates on the final Rig.

Uses the regenerated Motion Studio calibration/reference bound to the repaired
source GLB. Shoulder/elbow/wrist geometry is a provisional First Position
scaffold; Hand_L/R are aligned to continue the forearm line, then all five
finger chains are shaped independently from the canonical finger mapping.

This is a static visual/geometry candidate sweep only. It does not author the
49-frame path and does not claim ballet-teacher approval.
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
sys.path.insert(0, str(MOTION_TOOLS))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from accepted_arm_reference import extract_accepted_arm_reference  # noqa: E402
from accepted_arm_visual import joint_targets  # noqa: E402
from accepted_arm_visual_v0_6 import measured_hand_mesh_projection  # noqa: E402
from first_position_candidate import guide_first_position  # noqa: E402
from hand_clearance_candidate import shifted_solution  # noqa: E402
from rig_calibration import validate_calibration  # noqa: E402
from static_pose import dot  # noqa: E402
from static_pose_preview_v0_3 import apply_solution, render_views, require  # noqa: E402


SHAPE_LEVELS = {
    "soft": 0.70,
    "balanced": 1.00,
    "expressive": 1.30,
}


def normalized(v: Vector) -> Vector:
    require(v.length > 1e-8, "Degenerate vector")
    return v.normalized()


def angle_deg(a: Vector, b: Vector) -> float:
    a = normalized(a)
    b = normalized(b)
    return round(math.degrees(math.acos(max(-1.0, min(1.0, a.dot(b))))), 6)


def aim_bone(armature, bone_name: str, target_direction: Vector) -> None:
    bpy.context.view_layer.update()
    bone = armature.pose.bones[bone_name]
    head = bone.head.copy()
    current = normalized(bone.tail - head)
    target = normalized(target_direction)
    rotation = current.rotation_difference(target).to_matrix().to_4x4()
    bone.matrix = Matrix.Translation(head) @ rotation @ Matrix.Translation(-head) @ bone.matrix.copy()
    bpy.context.view_layer.update()


def align_hand_to_forearm(armature, solution, side: str) -> float:
    arm = solution["arms"][side]
    forearm_name = arm["bone_names"][1]
    hand_name = arm["bone_names"][2]
    bpy.context.view_layer.update()
    forearm = armature.pose.bones[forearm_name]
    hand = armature.pose.bones[hand_name]
    target = normalized(hand.head - forearm.head)
    aim_bone(armature, hand_name, target)
    bpy.context.view_layer.update()
    hand = armature.pose.bones[hand_name]
    return angle_deg(hand.head - forearm.head, hand.tail - hand.head)


def blend_dir(base: Vector, *terms: tuple[Vector, float]) -> Vector:
    v = base.copy()
    for axis, amount in terms:
        v += axis * amount
    return normalized(v)


def shape_finger_chain(armature, chain, base_target: Vector, bend_axis: Vector,
                       bend1: float, bend2: float) -> None:
    first, second, third = chain
    aim_bone(armature, first, base_target)
    bpy.context.view_layer.update()

    # Progressively curve the finger; small distributed curvature avoids spoon
    # hand while also avoiding a claw-like single-joint kink.
    first_dir = normalized(armature.pose.bones[first].tail - armature.pose.bones[first].head)
    aim_bone(armature, second, blend_dir(first_dir, (bend_axis, bend1)))
    bpy.context.view_layer.update()
    second_dir = normalized(armature.pose.bones[second].tail - armature.pose.bones[second].head)
    aim_bone(armature, third, blend_dir(second_dir, (bend_axis, bend2)))


def shape_ballet_hand(armature, mapping, calibration, solution, side: str, strength: float) -> dict:
    frame = calibration["anatomical_frame"]
    up = Vector(frame["up"])
    front = Vector(frame["front"])
    left = Vector(frame["left"])
    inward = -left if side == "left" else left

    arm = solution["arms"][side]
    hand_name = mapping["hands"][side]["hand"]
    hand = armature.pose.bones[hand_name]
    hand_forward = normalized(hand.tail - hand.head)

    # Natural first-position finger fan. Index extends the hand line; middle is
    # slightly lower/inward; ring and pinky follow with a graduated curve.
    targets = {
        "index": blend_dir(hand_forward, (up, +0.055 * strength), (inward, +0.025 * strength)),
        "middle": blend_dir(hand_forward, (up, -0.020 * strength), (inward, +0.065 * strength)),
        "ring": blend_dir(hand_forward, (up, -0.050 * strength), (inward, +0.050 * strength)),
        "pinky": blend_dir(hand_forward, (up, -0.080 * strength), (inward, +0.025 * strength)),
    }

    # A subtle anterior component creates a three-dimensional oval instead of a
    # flat spoon-hand silhouette. Distributed bend remains intentionally small.
    curl_axis = normalized(front + up * -0.20)
    shape_finger_chain(armature, mapping["hands"][side]["index"], targets["index"], curl_axis,
                       0.035 * strength, 0.025 * strength)
    shape_finger_chain(armature, mapping["hands"][side]["middle"], targets["middle"], curl_axis,
                       0.055 * strength, 0.040 * strength)
    shape_finger_chain(armature, mapping["hands"][side]["ring"], targets["ring"], curl_axis,
                       0.065 * strength, 0.050 * strength)
    shape_finger_chain(armature, mapping["hands"][side]["pinky"], targets["pinky"], curl_axis,
                       0.075 * strength, 0.060 * strength)

    # Thumb aims softly toward the middle finger's second-joint region without
    # touching it. Blend with the hand line to avoid a hard tucked-thumb kink.
    thumb_chain = mapping["hands"][side]["thumb"]
    middle_chain = mapping["hands"][side]["middle"]
    thumb = armature.pose.bones[thumb_chain[0]]
    middle_joint = armature.pose.bones[middle_chain[1]].head.copy()
    thumb_to_middle = normalized(middle_joint - thumb.head)
    thumb_base = normalized(hand_forward * (1.0 - 0.42 * strength) + thumb_to_middle * (0.42 * strength))
    shape_finger_chain(armature, thumb_chain, thumb_base, curl_axis,
                       0.070 * strength, 0.050 * strength)

    bpy.context.view_layer.update()

    tips = {}
    for finger, chain in mapping["hands"][side].items():
        if finger == "hand":
            continue
        bone = armature.pose.bones[chain[-1]]
        tips[finger] = [round(float(v), 8) for v in bone.tail]

    forearm_name = arm["bone_names"][1]
    forearm = armature.pose.bones[forearm_name]
    hand = armature.pose.bones[hand_name]
    continuity = angle_deg(hand.head - forearm.head, hand.tail - hand.head)

    return {
        "hand_bone": hand_name,
        "forearm_to_hand_continuity_deg": continuity,
        "finger_tips_armature": tips,
    }


def reset_pose(armature):
    for bone in armature.pose.bones:
        bone.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def build_first_scaffold(reference, calibration, shift: float):
    frame = calibration["anatomical_frame"]
    # Bras-bas is used only as the lower vertical/front boundary for First
    # Position. Re-solving that accepted endpoint after a lateral shift is both
    # unnecessary and, on the repaired real rig, can hit the two-link solver
    # boundary. Keep the exact accepted bras-bas geometry as the low bound.
    low = joint_targets(reference, calibration, "bras_bas")
    # First Position inherits its lateral wrist separation from the high
    # en-avant scaffold, so only that endpoint needs the bounded outward shift.
    high = shifted_solution(
        joint_targets(reference, calibration, "en_avant"),
        frame,
        shift,
        "body_outward",
    )
    height = dot(calibration["canonical_bones"]["spine_mid"]["head_local"], frame["up"])
    return guide_first_position(low, high, frame, navel_region_height=height)


def pose_candidate(armature, calibration, mapping, reference, shift: float, strength: float):
    reset_pose(armature)
    candidate = build_first_scaffold(reference, calibration, shift)
    residuals = apply_solution(armature, candidate)
    continuity = {}
    hand_shapes = {}
    for side in ("left", "right"):
        continuity[side] = align_hand_to_forearm(armature, candidate, side)
        hand_shapes[side] = shape_ballet_hand(armature, mapping, calibration, candidate, side, strength)
    projection = measured_hand_mesh_projection(armature, calibration)
    return candidate, residuals, continuity, hand_shapes, projection


def main():
    parser = argparse.ArgumentParser()
    for name in ("repo", "calibration", "reference", "source-profile", "mapping", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:])

    repo = args.repo.resolve()
    output = args.output.resolve()
    calibration = json.loads(args.calibration.read_text(encoding="utf-8"))
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    rig = json.loads((repo / "tools/motion_studio/low_poly_girl_rig_profile_v0.json").read_text(encoding="utf-8"))
    seed = json.loads((repo / rig["calibration_seed"]).read_text(encoding="utf-8"))
    validate_calibration(calibration, rig, seed, repo)

    reference = json.loads(args.reference.read_text(encoding="utf-8"))
    require(reference == extract_accepted_arm_reference(args.source_profile.read_bytes(), calibration),
            "Reference differs from regenerated accepted Phase 10 source")
    require(mapping.get("source_glb_sha256") == reference["source_glb_sha256"],
            "Finger mapping source SHA does not match regenerated reference")

    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(repo / rig["source_glb"]))
    armatures = [obj for obj in bpy.context.scene.objects
                 if obj.type == "ARMATURE" and obj.name == rig["armature"]]
    require(len(armatures) == 1, "Expected exactly one final Rig")
    armature = armatures[0]
    armature.animation_data_clear()
    bpy.context.scene.frame_set(1)

    for side in ("left", "right"):
        for finger, chain in mapping["hands"][side].items():
            names = [chain] if isinstance(chain, str) else chain
            for name in names:
                require(name in armature.pose.bones, f"Missing mapped bone {name}")

    output.mkdir(parents=True, exist_ok=True)
    results = {}

    # Search only enough lateral separation to prevent frontal hand overlap.
    # This keeps the provisional First Position arm oval compact.
    base_reach = joint_targets(reference, calibration, "en_avant")["arms"]["left"]["arm_reach"]
    tolerance = base_reach * 0.005
    # Start from zero separation adjustment. Bras-bas is no longer unnecessarily
    # re-solved; only the en-avant-derived lateral scaffold is shifted as needed.
    shift = 0.0
    print(f"FIRST_FINGER_SEARCH_INITIAL_SHIFT={shift:.8f}")
    for search_iteration in range(1, 13):
        _, _, _, _, probe = pose_candidate(
            armature, calibration, mapping, reference, shift, SHAPE_LEVELS["balanced"]
        )
        if probe["projected_gap_armature_units"] >= 0.005:
            break
        shift += max((0.005 - probe["projected_gap_armature_units"]) / 2.0, tolerance)
    else:
        raise RuntimeError("Could not find bounded First Position hand separation")

    for label, strength in SHAPE_LEVELS.items():
        candidate, residuals, continuity, hand_shapes, projection = pose_candidate(
            armature, calibration, mapping, reference, shift, strength
        )
        previews = render_views(armature, calibration, output, prefix=f"first_fingers_{label}")
        results[label] = {
            "shape_strength": strength,
            "outward_shift_per_wrist_armature_units": round(shift, 8),
            "arm_residuals": residuals,
            "hand_continuity_deg": continuity,
            "hand_shape": hand_shapes,
            "hand_mesh_projection": projection,
            "previews": previews,
        }

    blend = output / "first_position_finger_aware_candidates_v0_7.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(blend))
    report = {
        "status": "FIRST_POSITION_FINGER_AWARE_VISUAL_REVIEW_REQUIRED",
        "source_profile_sha256": reference["source_profile_sha256"],
        "source_glb_sha256": reference["source_glb_sha256"],
        "finger_mapping_profile_id": mapping["profile_id"],
        "contract": "tools/motion_studio/BALLET_HAND_FORM_CONTRACT.md",
        "scaffold": {
            "wrist_height": "calibrated spine_mid head elevation torso proxy",
            "hand_root_policy": "Hand bone aligned to continue forearm direction",
            "outward_shift_search_iterations": search_iteration,
            "outward_shift_per_wrist_armature_units": round(shift, 8),
        },
        "candidates": results,
        "blend": str(blend),
        "limits": (
            "Static First Position candidate sweep only. Finger shaping is procedural and "
            "requires front/side visual review. No teacher approval, 3D collision guarantee, "
            "physiological joint-limit proof, temporal smoothing or 49-frame path authored."
        ),
    }
    report_path = output / "report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("MOTION_STUDIO_FIRST_POSITION_FINGERS=VISUAL_REVIEW_REQUIRED")
    print(f"SOURCE_SHA256={reference['source_glb_sha256']}")
    print(f"SHIFT={round(shift, 8)}")
    print(f"REPORT={report_path}")
    for label, item in results.items():
        print(f"{label.upper()}_GAP={item['hand_mesh_projection']['projected_gap_armature_units']}")
        print(f"{label.upper()}_LEFT_CONTINUITY_DEG={item['hand_continuity_deg']['left']}")
        print(f"{label.upper()}_RIGHT_CONTINUITY_DEG={item['hand_continuity_deg']['right']}")
        print(f"{label.upper()}_FRONT={item['previews']['front']}")
        print(f"{label.upper()}_SIDE={item['previews']['side']}")
    print(f"BLEND={blend}")


if __name__ == "__main__":
    main()
