"""Phase 10.7.1 bras_bas -> en_avant foundation-motion prototype.

The accepted Phase 10.6 static realization remains the endpoint authority.
This script captures those exact realized rig states and connects only the
actual humanoid upper-body chain with deterministic motion: shortest-arc
shoulder motion, a parent-aware armature-space rounded waypoint for the
elbow/forearm, shortest-arc finger motion, and canonical 2DOF wrist reconstruction. It does not export GLB or touch gameplay/choreography
systems.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


PHASE = "10.7.1"
HERE = Path(__file__).resolve().parent
REPO_DEFAULT = HERE.parents[1]
BALLET_TOOLS = REPO_DEFAULT / "tools" / "ballet_motion"
for path in (HERE, BALLET_TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402
import render_foundation_pose_visual_gate_v1 as visual_gate  # noqa: E402
import foundation_motion as motion  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--canonical-profile", required=True)
    parser.add_argument("--constraint-profile", required=True)
    parser.add_argument("--retarget-profile", required=True)
    parser.add_argument("--retarget-axis-contract", required=True)
    parser.add_argument("--grammar-profile", required=True)
    parser.add_argument("--intent-spec", required=True)
    parser.add_argument("--static-contract", required=True)
    parser.add_argument("--visual-contract", required=True)
    parser.add_argument("--motion-contract", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--preview-dir", required=True)
    return parser.parse_args(sys.argv[sys.argv.index("--") + 1:])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def matrix_max_error(a: Matrix, b: Matrix) -> float:
    return max(
        abs(float(a[row][col]) - float(b[row][col]))
        for row in range(4)
        for col in range(4)
    )


def snapshot_local_pose(armature: bpy.types.Object) -> dict[str, Matrix]:
    return {
        bone.name: bone.matrix_basis.copy()
        for bone in armature.pose.bones
    }


def snapshot_pose_matrices(
    armature: bpy.types.Object,
    rig_names: list[str],
) -> dict[str, Matrix]:
    return {
        name: armature.pose.bones[name].matrix.copy()
        for name in rig_names
    }


def actual_upper_chain(
    armature: bpy.types.Object,
    canonical: dict,
    static_contract: dict,
) -> tuple[dict[str, str], dict]:
    roles: dict[str, str] = {}
    evidence = {"sides": {}}
    digits = list(static_contract["ballet_hand_shape"]["digits"])

    for side in ("left", "right"):
        upper = canonical["canonical_bones"][f"{side}_upper_arm"]["rig_bone"]
        forearm = canonical["canonical_bones"][f"{side}_forearm"]["rig_bone"]
        hand = canonical["canonical_bones"][f"{side}_hand"]["rig_bone"]

        roles[upper] = "shoulder"
        roles[forearm] = "elbow"
        roles[hand] = "wrist"

        chains = {
            digit: static_core._finger_chain_from_hand_hierarchy(
                armature,
                hand,
                digit,
            )
            for digit in digits
        }
        finger_names = []
        for digit in digits:
            for rig_name in chains[digit]:
                roles[rig_name] = "fingers"
                if rig_name not in finger_names:
                    finger_names.append(rig_name)

        evidence["sides"][side] = {
            "upper_arm": upper,
            "forearm": forearm,
            "hand": hand,
            "finger_chains": chains,
            "finger_order_authority": "ACTUAL_RIG_HIERARCHY_DEPTH",
        }

    return roles, evidence


def realize_endpoint(
    pose_name: str,
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    retarget: dict,
    retarget_axis_contract: dict,
    static_contract: dict,
    visual_contract: dict,
    runtime: dict,
) -> tuple[dict[str, Matrix], dict]:
    realization = visual_gate.realize_pose(
        pose_name,
        armature,
        canonical,
        constraints,
        retarget,
        retarget_axis_contract,
        static_contract,
        runtime,
    )
    wrist = visual_gate.validate_hand_axial_continuity(
        armature,
        canonical,
        constraints,
        visual_contract,
    )
    return snapshot_local_pose(armature), {
        "realization": realization,
        "wrist_continuity": wrist,
    }


def _blend_numeric_mapping(
    start: dict,
    end: dict,
    fraction: float,
) -> dict:
    require(
        set(start) == set(end),
        f"Waypoint mapping keys differ: {sorted(start)} != {sorted(end)}.",
    )
    return {
        key: motion.interpolate_bounded_scalar(
            float(start[key]),
            float(end[key]),
            fraction,
        )
        for key in start
    }


def build_rounded_waypoint_intent(
    start_intent: dict,
    end_intent: dict,
    contract: dict,
) -> dict:
    waypoint_contract = contract["interpolation"][
        "rounded_transition_waypoint"
    ]
    fraction = float(waypoint_contract["semantic_fraction"])

    require(
        start_intent["kind"] == "symmetric_arm_chain"
        and end_intent["kind"] == "symmetric_arm_chain",
        "Rounded waypoint requires symmetric arm-chain endpoints.",
    )
    require(
        abs(
            float(start_intent["elbow_angle_deg"])
            - float(end_intent["elbow_angle_deg"])
        )
        <= 1e-12,
        "Rounded waypoint may not invent a new elbow angle.",
    )
    require(
        start_intent.get("centerline_hand_policy")
        == end_intent.get("centerline_hand_policy"),
        "Rounded waypoint requires matching endpoint centerline policy.",
    )
    require(
        start_intent.get("hand_mesh_gap_chain_fraction")
        == end_intent.get("hand_mesh_gap_chain_fraction"),
        "Rounded waypoint requires matching endpoint hand-gap contract.",
    )

    intent = copy.deepcopy(start_intent)
    intent["wrist_direction"] = _blend_numeric_mapping(
        start_intent["wrist_direction"],
        end_intent["wrist_direction"],
        fraction,
    )
    intent["hand_direction"] = _blend_numeric_mapping(
        start_intent["hand_direction"],
        end_intent["hand_direction"],
        fraction,
    )
    # Preserve the accepted bras-bas elbow pole through the midpoint. The
    # visual rejection showed that rotating this bend plane too early makes
    # the arm read as a forward push instead of a rounded port de bras.
    intent["elbow_pole"] = copy.deepcopy(start_intent["elbow_pole"])

    intent["joint_dofs"] = {}
    for joint_name in start_intent["joint_dofs"]:
        require(
            joint_name in end_intent["joint_dofs"],
            f"Waypoint joint missing from end intent: {joint_name}.",
        )
        intent["joint_dofs"][joint_name] = _blend_numeric_mapping(
            start_intent["joint_dofs"][joint_name],
            end_intent["joint_dofs"][joint_name],
            fraction,
        )
    return intent


def realize_rounded_waypoint(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    retarget_axis_contract: dict,
    static_contract: dict,
    visual_contract: dict,
    runtime: dict,
    contract: dict,
) -> tuple[dict[str, Matrix], dict[str, Matrix], dict]:
    start_name = contract["transition"]["start_pose"]
    end_name = contract["transition"]["end_pose"]
    waypoint_name = "__phase10_7_rounded_transition_waypoint"

    waypoint_intent = build_rounded_waypoint_intent(
        runtime["intent_spec"]["poses"][start_name],
        runtime["intent_spec"]["poses"][end_name],
        contract,
    )
    temp_intents = copy.deepcopy(runtime["intent_spec"])
    temp_grammar = copy.deepcopy(runtime["grammar_profile"])
    temp_intents["poses"][waypoint_name] = waypoint_intent
    temp_grammar["poses"][waypoint_name] = copy.deepcopy(
        temp_grammar["poses"][start_name]
    )

    solution = runtime["pose_solver"].solve_pose(
        waypoint_name,
        temp_intents,
        temp_grammar,
        canonical,
        constraints,
    )
    pose_entry = runtime["retarget_solver"].retarget_pose_solution(
        solution,
        canonical,
        constraints,
        retarget_axis_contract,
    )
    static_core.apply_rotation_deltas(armature, pose_entry)
    hand_shape = static_core.apply_ballet_hand_shape(
        armature,
        canonical,
        static_contract,
    )
    wrist = visual_gate.validate_hand_axial_continuity(
        armature,
        canonical,
        constraints,
        visual_contract,
    )

    waypoint_pose = snapshot_local_pose(armature)
    waypoint_absolute_bases = {
        canonical["canonical_bones"][f"{side}_forearm"]["rig_bone"]:
            static_core.normalized_basis(
                armature.pose.bones[
                    canonical["canonical_bones"][f"{side}_forearm"]["rig_bone"]
                ].matrix
            )
        for side in ("left", "right")
    }
    elbows = {}
    for side in ("left", "right"):
        elbows[side] = elbow_opening_deg(
            armature,
            canonical["canonical_bones"][f"{side}_upper_arm"]["rig_bone"],
            canonical["canonical_bones"][f"{side}_forearm"]["rig_bone"],
        )
    return waypoint_pose, waypoint_absolute_bases, {
        "name": waypoint_name,
        "semantic_fraction": float(
            contract["interpolation"]["rounded_transition_waypoint"][
                "semantic_fraction"
            ]
        ),
        "intent_rule": contract["interpolation"][
            "rounded_transition_waypoint"
        ]["intent_rule"],
        "application_space": contract["interpolation"][
            "rounded_transition_waypoint"
        ]["application_space"],
        "parent_pose_assumption": contract["interpolation"][
            "rounded_transition_waypoint"
        ]["parent_pose_assumption"],
        "elbow_angle_deg": elbows,
        "canonical_solver": solution["evidence"],
        "retarget": pose_entry["evidence"],
        "wrist_continuity": wrist,
        "ballet_hand_shape": hand_shape,
        "endpoint_authority_mutated": False,
    }


def prepare_motion_cache(
    armature: bpy.types.Object,
    roles: dict[str, str],
    start_pose: dict[str, Matrix],
    end_pose: dict[str, Matrix],
    waypoint_pose: dict[str, Matrix],
    waypoint_absolute_bases: dict[str, Matrix],
    contract: dict,
) -> dict:
    translation_limit = float(
        contract["validation"]["moving_translation_error_max"]
    )
    scale_limit = float(
        contract["validation"]["moving_scale_error_max"]
    )
    cache = {}

    for rig_name, role in roles.items():
        start_loc, start_q, start_scale = start_pose[rig_name].decompose()
        end_loc, end_q, end_scale = end_pose[rig_name].decompose()
        translation_error = (end_loc - start_loc).length
        scale_error = (end_scale - start_scale).length
        require(
            translation_error <= translation_limit,
            f"{rig_name}: moving bone local translation changed "
            f"{translation_error} > {translation_limit}.",
        )
        require(
            scale_error <= scale_limit,
            f"{rig_name}: moving bone local scale changed "
            f"{scale_error} > {scale_limit}.",
        )

        start_q.normalize()
        end_q.normalize()
        if start_q.dot(end_q) < 0.0:
            end_q.negate()

        item = {
            "role": role,
            "location": start_loc.copy(),
            "scale": start_scale.copy(),
            "start_quaternion": start_q.copy(),
            "end_quaternion": end_q.copy(),
            "endpoint_angle_deg": math.degrees(
                start_q.rotation_difference(end_q).angle
            ),
        }
        if role in contract["interpolation"][
            "rounded_transition_waypoint"
        ]["affected_roles"]:
            waypoint_loc, _waypoint_q, waypoint_scale = (
                waypoint_pose[rig_name].decompose()
            )
            require(
                (waypoint_loc - start_loc).length <= translation_limit,
                f"{rig_name}: waypoint local translation changed.",
            )
            require(
                (waypoint_scale - start_scale).length <= scale_limit,
                f"{rig_name}: waypoint local scale changed.",
            )
            require(
                rig_name in waypoint_absolute_bases,
                f"{rig_name}: absolute forearm waypoint basis missing.",
            )
            item["waypoint_armature_basis"] = (
                waypoint_absolute_bases[rig_name].copy()
            )
        cache[rig_name] = item
        armature.pose.bones[rig_name].rotation_mode = "QUATERNION"

    return cache


def prepare_wrist_2dof_cache(
    canonical: dict,
    start_evidence: dict,
    end_evidence: dict,
    motion_cache: dict,
) -> dict:
    cache = {}
    for side in ("left", "right"):
        rig_name = canonical["canonical_bones"][f"{side}_hand"]["rig_bone"]
        require(
            motion_cache[rig_name]["role"] == "wrist",
            f"{side}: canonical hand is not classified as wrist motion.",
        )
        start = start_evidence["wrist_continuity"][side]
        end = end_evidence["wrist_continuity"][side]
        cache[side] = {
            "rig_name": rig_name,
            "start_flexion_extension_deg": float(
                start["flexion_extension_deg"]
            ),
            "end_flexion_extension_deg": float(
                end["flexion_extension_deg"]
            ),
            "start_radial_ulnar_deviation_deg": float(
                start["radial_ulnar_deviation_deg"]
            ),
            "end_radial_ulnar_deviation_deg": float(
                end["radial_ulnar_deviation_deg"]
            ),
        }
    return cache


def apply_wrist_2dof_interpolation(
    armature: bpy.types.Object,
    canonical: dict,
    motion_cache: dict,
    wrist_cache: dict,
    trace: dict[str, float],
    frame: int,
    frame_start: int,
    frame_end: int,
) -> dict:
    progress = float(trace["wrist"])
    evidence = {
        "frame": int(frame),
        "progress": progress,
        "endpoint_matrix_preserved": frame in (frame_start, frame_end),
        "sides": {},
    }

    # Accepted Phase 10.6 endpoint matrices remain exact authority. The
    # canonical 2DOF reconstruction is used only between those endpoints.
    if frame in (frame_start, frame_end):
        return evidence

    for side, item in wrist_cache.items():
        flexion = motion.interpolate_bounded_scalar(
            item["start_flexion_extension_deg"],
            item["end_flexion_extension_deg"],
            progress,
        )
        deviation = motion.interpolate_bounded_scalar(
            item["start_radial_ulnar_deviation_deg"],
            item["end_radial_ulnar_deviation_deg"],
            progress,
        )
        static_core.apply_hand_wrist_candidate(
            armature,
            canonical,
            side,
            flexion,
            deviation,
        )

        rig_name = item["rig_name"]
        hand = armature.pose.bones[rig_name]
        hand.location = motion_cache[rig_name]["location"].copy()
        hand.scale = motion_cache[rig_name]["scale"].copy()
        bpy.context.view_layer.update()

        evidence["sides"][side] = {
            "flexion_extension_deg": float(flexion),
            "radial_ulnar_deviation_deg": float(deviation),
            "independent_axial_roll": "BLOCKED",
        }

    return evidence


def apply_parent_aware_elbow_waypoint(
    armature: bpy.types.Object,
    motion_cache: dict,
    waypoint_weight: float,
) -> None:
    weight = float(waypoint_weight)
    if weight <= 0.0:
        return

    for rig_name, item in motion_cache.items():
        target_basis = item.get("waypoint_armature_basis")
        if target_basis is None:
            continue

        bone = armature.pose.bones[rig_name]
        current_basis = static_core.normalized_basis(bone.matrix)
        current_q = current_basis.to_quaternion()
        target_q = target_basis.to_quaternion()
        current_q.normalize()
        target_q.normalize()
        if current_q.dot(target_q) < 0.0:
            target_q.negate()

        desired_basis = current_q.slerp(
            target_q,
            weight,
        ).to_matrix()
        static_core.apply_absolute_rig_rotation_via_matrix_basis(
            armature,
            rig_name,
            desired_basis,
        )
        bone.location = item["location"].copy()
        bone.scale = item["scale"].copy()
        bpy.context.view_layer.update()


def set_interpolated_pose(
    armature: bpy.types.Object,
    start_pose: dict[str, Matrix],
    motion_cache: dict,
    frame: int,
    contract: dict,
) -> dict[str, float]:
    trace = motion.progress_trace(frame, contract)
    normalized_t = motion.normalized_time(frame, contract)
    waypoint_weight = motion.compact_minimum_jerk_waypoint_weight(
        normalized_t,
        contract["interpolation"]["rounded_transition_waypoint"],
    )
    moving = set(motion_cache)

    for bone in armature.pose.bones:
        if bone.name not in moving:
            bone.matrix_basis = start_pose[bone.name].copy()

    for rig_name, item in motion_cache.items():
        progress = float(trace[item["role"]])
        bone = armature.pose.bones[rig_name]
        bone.rotation_mode = "QUATERNION"
        bone.location = item["location"]
        bone.scale = item["scale"]
        if progress <= 0.0:
            q = item["start_quaternion"].copy()
        elif progress >= 1.0:
            q = item["end_quaternion"].copy()
        else:
            q = item["start_quaternion"].slerp(
                item["end_quaternion"],
                progress,
            )
        q.normalize()
        bone.rotation_quaternion = q

    bpy.context.view_layer.update()
    apply_parent_aware_elbow_waypoint(
        armature,
        motion_cache,
        waypoint_weight,
    )
    return trace


def enforce_hand_centerline_clearance(
    armature: bpy.types.Object,
    canonical: dict,
    runtime: dict,
    contract: dict,
    motion_cache: dict,
    frame: int,
    frame_start: int,
    frame_end: int,
) -> dict:
    projection = contract["validation"]["centerline_clearance_projection"]
    samples = runtime["hand_samples"]
    inner_q = float(runtime["hand_sampling"]["inner_edge_quantile"])
    minimum = float(contract["validation"]["minimum_hand_mesh_side_offset"])
    guard = float(projection["intermediate_guard_side_offset"])
    target = minimum if frame in (frame_start, frame_end) else max(minimum, guard)

    result = {
        "frame": int(frame),
        "target_side_offset": float(target),
        "sides": {},
    }
    frame_axes = canonical["body_frame"]["declared_axes_armature_local"]
    axis_vectors = {
        name: Vector(frame_axes[name]).normalized()
        for name in projection["candidate_axes"]
    }
    max_angle = float(projection["maximum_shoulder_correction_deg"])
    iterations = int(projection["bisection_iterations"])

    for side in ("left", "right"):
        measurement = static_core.hand_mesh_inner_edge(
            armature,
            canonical,
            samples[side],
            side,
            inner_q,
        )
        initial_offset = float(measurement["side_offset"])
        side_result = {
            "initial_side_offset": initial_offset,
            "correction_applied": False,
            "axis": None,
            "angle_deg": 0.0,
            "final_side_offset": initial_offset,
        }
        result["sides"][side] = side_result

        # Exact Phase 10.6 endpoint matrices remain authoritative. Endpoints
        # are checked against the hard no-crossing floor but never projected.
        if frame in (frame_start, frame_end):
            require(
                initial_offset >= minimum - 1e-9,
                f"Frame {frame}: accepted {side} endpoint crosses centerline "
                f"({initial_offset}).",
            )
            continue

        if initial_offset >= target - 1e-9:
            continue

        shoulder_name = canonical["canonical_bones"][
            f"{side}_upper_arm"
        ]["rig_bone"]
        shoulder = armature.pose.bones[shoulder_name]
        baseline = shoulder.matrix_basis.copy()
        baseline_location, _baseline_q, baseline_scale = baseline.decompose()

        def restore_baseline() -> None:
            shoulder.matrix_basis = baseline.copy()
            bpy.context.view_layer.update()

        def evaluate(axis_name: str, angle_deg: float) -> dict:
            restore_baseline()
            static_core.apply_single_shoulder_sweep(
                armature,
                canonical,
                side,
                axis_vectors[axis_name],
                angle_deg,
            )
            # The clearance projection is rotational only. Preserve the
            # interpolated translation/scale contract exactly.
            shoulder.location = baseline_location.copy()
            shoulder.scale = baseline_scale.copy()
            bpy.context.view_layer.update()
            measured = static_core.hand_mesh_inner_edge(
                armature,
                canonical,
                samples[side],
                side,
                inner_q,
            )
            return {
                "axis": axis_name,
                "angle_deg": float(angle_deg),
                "side_offset": float(measured["side_offset"]),
            }

        brackets = []
        for axis_name in axis_vectors:
            for endpoint_angle in (-max_angle, max_angle):
                candidate = evaluate(axis_name, endpoint_angle)
                if candidate["side_offset"] >= target:
                    brackets.append(candidate)

        require(
            bool(brackets),
            f"Frame {frame}: {side} hand centerline clearance cannot be "
            f"restored within +/-{max_angle} deg shoulder projection; "
            f"initial={initial_offset}, target={target}.",
        )

        solutions = []
        for bracket in brackets:
            axis_name = bracket["axis"]
            low = 0.0
            high = float(bracket["angle_deg"])
            for _ in range(iterations):
                mid = (low + high) * 0.5
                candidate = evaluate(axis_name, mid)
                if candidate["side_offset"] >= target:
                    high = mid
                else:
                    low = mid
            solution = evaluate(axis_name, high)
            solutions.append(solution)

        best = min(
            solutions,
            key=lambda item: (
                abs(float(item["angle_deg"])),
                abs(float(item["side_offset"]) - target),
                item["axis"],
            ),
        )
        final = evaluate(best["axis"], float(best["angle_deg"]))
        require(
            final["side_offset"] >= minimum - 1e-9,
            f"Frame {frame}: {side} clearance projection failed; "
            f"final={final['side_offset']}.",
        )

        # Explicitly reassert the motion-cache scale/location authority after
        # the projection, in case Blender decomposed the rotation assignment.
        shoulder.location = motion_cache[shoulder_name]["location"].copy()
        shoulder.scale = motion_cache[shoulder_name]["scale"].copy()
        bpy.context.view_layer.update()
        final_measurement = static_core.hand_mesh_inner_edge(
            armature,
            canonical,
            samples[side],
            side,
            inner_q,
        )
        final_offset = float(final_measurement["side_offset"])
        require(
            final_offset >= minimum - 1e-9,
            f"Frame {frame}: {side} final hand crossed centerline "
            f"after scale/location restore ({final_offset}).",
        )

        side_result.update(
            {
                "correction_applied": True,
                "axis": best["axis"],
                "angle_deg": float(best["angle_deg"]),
                "final_side_offset": final_offset,
            }
        )

    return result


def key_motion(
    armature: bpy.types.Object,
    canonical: dict,
    runtime: dict,
    start_pose: dict[str, Matrix],
    motion_cache: dict,
    wrist_cache: dict,
    contract: dict,
) -> tuple[int, int, dict]:
    frame_start = int(contract["transition"]["frame_start"])
    frame_end = motion.frame_end(contract)

    if armature.animation_data is not None:
        armature.animation_data_clear()

    clearance_frames = []
    wrist_frames = []
    for frame in range(frame_start, frame_end + 1):
        trace = set_interpolated_pose(
            armature,
            start_pose,
            motion_cache,
            frame,
            contract,
        )
        wrist_evidence = apply_wrist_2dof_interpolation(
            armature,
            canonical,
            motion_cache,
            wrist_cache,
            trace,
            frame,
            frame_start,
            frame_end,
        )
        if frame not in (frame_start, frame_end):
            wrist_frames.append(wrist_evidence)

        clearance = enforce_hand_centerline_clearance(
            armature,
            canonical,
            runtime,
            contract,
            motion_cache,
            frame,
            frame_start,
            frame_end,
        )
        if any(
            item["correction_applied"]
            for item in clearance["sides"].values()
        ):
            clearance_frames.append(clearance)

        for rig_name in motion_cache:
            bone = armature.pose.bones[rig_name]
            bone.keyframe_insert(data_path="location", frame=frame)
            bone.keyframe_insert(
                data_path="rotation_quaternion",
                frame=frame,
            )
            bone.keyframe_insert(data_path="scale", frame=frame)

    scene = bpy.context.scene
    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = int(contract["transition"]["fps"])
    scene.frame_set(frame_start)
    return frame_start, frame_end, {
        "rounded_elbow_waypoint": {
            "method": contract["interpolation"]["rotation"]["elbow"],
            "application_space": contract["interpolation"][
                "rounded_transition_waypoint"
            ]["application_space"],
            "parent_pose_assumption": contract["interpolation"][
                "rounded_transition_waypoint"
            ]["parent_pose_assumption"],
            "activation_start": float(
                contract["interpolation"]["rounded_transition_waypoint"][
                    "activation_start"
                ]
            ),
            "activation_center": float(
                contract["interpolation"]["rounded_transition_waypoint"][
                    "motion_progress"
                ]
            ),
            "activation_end": float(
                contract["interpolation"]["rounded_transition_waypoint"][
                    "activation_end"
                ]
            ),
        },
        "wrist_2dof_interpolation": {
            "method": "CANONICAL_WRIST_2DOF_COMPONENT_INTERPOLATION",
            "intermediate_only": True,
            "endpoint_matrix_preserved": True,
            "independent_axial_roll": "BLOCKED",
            "endpoint_dofs": wrist_cache,
            "sample_count": len(wrist_frames),
            "frames": wrist_frames,
        },
        "centerline_clearance_projection": {
            "method": "MINIMAL_DEFORMED_MESH_SHOULDER_PROJECTION",
            "intermediate_only": True,
            "endpoint_projection_forbidden": True,
            "corrected_frame_count": len(clearance_frames),
            "corrected_frames": clearance_frames,
        },
    }


def elbow_opening_deg(
    armature: bpy.types.Object,
    upper_name: str,
    forearm_name: str,
) -> float:
    upper = armature.pose.bones[upper_name]
    forearm = armature.pose.bones[forearm_name]
    shoulder = Vector(upper.head)
    elbow = Vector(forearm.head)
    wrist = Vector(forearm.tail)
    a = shoulder - elbow
    b = wrist - elbow
    require(a.length > 1e-9 and b.length > 1e-9, "Degenerate elbow chain.")
    return math.degrees(a.angle(b))


def endpoint_errors(
    armature: bpy.types.Object,
    target: dict[str, Matrix],
    moving_names: set[str],
) -> float:
    return max(
        matrix_max_error(
            armature.pose.bones[name].matrix_basis,
            target[name],
        )
        for name in moving_names
    )


def configure_video_output(scene: bpy.types.Scene) -> str:
    image_settings = scene.render.image_settings
    media_property = image_settings.bl_rna.properties.get("media_type")
    if media_property is not None:
        values = {item.identifier for item in media_property.enum_items}
        if "VIDEO" in values:
            image_settings.media_type = "VIDEO"
            return "MEDIA_TYPE_VIDEO"

    format_property = image_settings.bl_rna.properties.get("file_format")
    if format_property is not None:
        values = {item.identifier for item in format_property.enum_items}
        if "FFMPEG" in values:
            image_settings.file_format = "FFMPEG"
            return "FILE_FORMAT_FFMPEG"

    raise RuntimeError("Blender exposes no supported video output API.")


def validate_motion(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    intent_spec: dict,
    visual_contract: dict,
    runtime: dict,
    contract: dict,
    start_pose: dict[str, Matrix],
    end_pose: dict[str, Matrix],
    roles: dict[str, str],
    lower_reference: dict[str, Matrix],
    frame_start: int,
    frame_end: int,
) -> dict:
    moving = set(roles)
    locked = set(start_pose) - moving
    locked_limit = float(
        contract["validation"]["locked_local_matrix_error_max"]
    )
    lower_limit = float(
        contract["validation"]["locked_world_matrix_error_max"]
    )
    endpoint_limit = float(
        contract["validation"]["endpoint_local_matrix_error_max"]
    )
    min_elbow = float(
        contract["validation"]["minimum_elbow_opening_deg"]
    )
    max_elbow = float(
        contract["validation"]["maximum_elbow_opening_deg"]
    )
    min_hand_side = float(
        contract["validation"]["minimum_hand_mesh_side_offset"]
    )
    min_quat_dot = float(
        contract["validation"]["minimum_consecutive_quaternion_dot"]
    )

    frame_axis = canonical["body_frame"]["declared_axes_armature_local"]
    left_axis = Vector(frame_axis["left"]).normalized()
    samples = runtime["hand_samples"]
    inner_q = float(runtime["hand_sampling"]["inner_edge_quantile"])

    side_chain = {
        side: {
            "upper": canonical["canonical_bones"][f"{side}_upper_arm"]["rig_bone"],
            "forearm": canonical["canonical_bones"][f"{side}_forearm"]["rig_bone"],
        }
        for side in ("left", "right")
    }

    max_locked_error = 0.0
    max_lower_error = 0.0
    minimum_hand_side = float("inf")
    minimum_elbow_side = float("inf")
    elbow_range = [float("inf"), float("-inf")]
    minimum_q_dot = 1.0
    max_q_step_deg = 0.0
    previous_q = {}
    frames = []

    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()

        locked_error = max(
            matrix_max_error(
                armature.pose.bones[name].matrix_basis,
                start_pose[name],
            )
            for name in locked
        )
        max_locked_error = max(max_locked_error, locked_error)

        lower_error = max(
            matrix_max_error(
                armature.pose.bones[name].matrix,
                lower_reference[name],
            )
            for name in lower_reference
        )
        max_lower_error = max(max_lower_error, lower_error)

        hand_side_offsets = {}
        for side in ("left", "right"):
            measurement = static_core.hand_mesh_inner_edge(
                armature,
                canonical,
                samples[side],
                side,
                inner_q,
            )
            side_offset = float(measurement["side_offset"])
            hand_side_offsets[side] = side_offset
            minimum_hand_side = min(minimum_hand_side, side_offset)
            require(
                side_offset >= min_hand_side - 1e-9,
                f"Frame {frame}: {side} hand crossed centerline "
                f"({side_offset}).",
            )

        wrist = visual_gate.validate_hand_axial_continuity(
            armature,
            canonical,
            constraints,
            visual_contract,
        )

        elbows = {}
        for side in ("left", "right"):
            names = side_chain[side]
            opening = elbow_opening_deg(
                armature,
                names["upper"],
                names["forearm"],
            )
            elbows[side] = opening
            elbow_range[0] = min(elbow_range[0], opening)
            elbow_range[1] = max(elbow_range[1], opening)
            require(
                min_elbow <= opening <= max_elbow,
                f"Frame {frame}: {side} elbow opening {opening} "
                f"outside [{min_elbow}, {max_elbow}].",
            )
            elbow_point = Vector(
                armature.pose.bones[names["forearm"]].head
            )
            signed_side = float(elbow_point.dot(left_axis))
            if side == "right":
                signed_side = -signed_side
            minimum_elbow_side = min(minimum_elbow_side, signed_side)
            require(
                signed_side >= -1e-6,
                f"Frame {frame}: {side} elbow inverted across body centerline "
                f"({signed_side}).",
            )

        t = motion.normalized_time(frame, contract)
        semantic = motion.semantic_dof_proxy(
            t,
            contract,
            intent_spec,
            constraints,
        )
        require(
            semantic["status"] == "PASS",
            f"Frame {frame}: semantic preferred-envelope proxy failed.",
        )

        for rig_name in moving:
            q = armature.pose.bones[rig_name].matrix_basis.to_quaternion()
            q.normalize()
            prior = previous_q.get(rig_name)
            if prior is not None:
                dot = float(prior.dot(q))
                if dot < 0.0:
                    q.negate()
                    dot = float(prior.dot(q))
                minimum_q_dot = min(minimum_q_dot, dot)
                require(
                    dot >= min_quat_dot - 1e-9,
                    f"Frame {frame}: quaternion flip on {rig_name}: {dot}.",
                )
                step = math.degrees(prior.rotation_difference(q).angle)
                max_q_step_deg = max(max_q_step_deg, step)
            previous_q[rig_name] = q.copy()

        trace = motion.progress_trace(frame, contract)
        frames.append(
            {
                "frame": frame,
                "normalized_t": round(t, 8),
                "progress": {
                    key: round(float(value), 8)
                    for key, value in trace.items()
                },
                "hand_mesh_side_offset": {
                    key: round(value, 8)
                    for key, value in hand_side_offsets.items()
                },
                "elbow_opening_deg": {
                    key: round(value, 8)
                    for key, value in elbows.items()
                },
                "wrist_continuity": wrist,
                "semantic_preferred_envelope_proxy": semantic["status"],
                "locked_local_matrix_error": locked_error,
                "lower_chain_matrix_error": lower_error,
            }
        )

    require(
        max_locked_error <= locked_limit,
        f"Locked local drift {max_locked_error} > {locked_limit}.",
    )
    require(
        max_lower_error <= lower_limit,
        f"Lower body/root drift {max_lower_error} > {lower_limit}.",
    )

    bpy.context.scene.frame_set(frame_start)
    start_error = endpoint_errors(
        armature,
        start_pose,
        moving,
    )
    bpy.context.scene.frame_set(frame_end)
    end_error = endpoint_errors(
        armature,
        end_pose,
        moving,
    )
    require(
        start_error <= endpoint_limit,
        f"Start endpoint error {start_error} > {endpoint_limit}.",
    )
    require(
        end_error <= endpoint_limit,
        f"End endpoint error {end_error} > {endpoint_limit}.",
    )

    return {
        "start_endpoint_local_matrix_error": start_error,
        "end_endpoint_local_matrix_error": end_error,
        "maximum_locked_local_matrix_error": max_locked_error,
        "maximum_lower_body_root_matrix_error": max_lower_error,
        "minimum_hand_mesh_side_offset": minimum_hand_side,
        "minimum_elbow_body_side_offset": minimum_elbow_side,
        "elbow_opening_range_deg": elbow_range,
        "minimum_consecutive_quaternion_dot": minimum_q_dot,
        "maximum_consecutive_quaternion_step_deg": max_q_step_deg,
        "sample_count": len(frames),
        "sampled_every_frame": True,
        "frames": frames,
    }


def render_previews(
    armature: bpy.types.Object,
    canonical: dict,
    contract: dict,
    preview_dir: Path,
    frame_start: int,
    frame_end: int,
) -> tuple[list[str], dict]:
    preview_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    resolution = int(contract["preview"]["resolution"])
    engine = visual_gate.configure_workbench(scene, resolution)
    video_api = configure_video_output(scene)

    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = int(contract["transition"]["fps"])
    scene.render.ffmpeg.format = contract["preview"]["container"]
    scene.render.ffmpeg.codec = contract["preview"]["codec"]
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"

    camera, center_world, height = visual_gate.create_camera(
        armature,
        canonical,
    )
    paths = []
    for view_name in contract["preview"]["views"]:
        visual_gate.set_view(
            camera,
            center_world,
            armature,
            canonical,
            view_name,
            height,
        )
        path = preview_dir / (
            f"bras_bas_to_en_avant_{view_name.lower()}.mp4"
        )
        if path.exists():
            path.unlink()
        scene.render.filepath = str(path)
        result = bpy.ops.render.render(animation=True)
        require(
            "FINISHED" in result,
            f"{view_name}: preview render failed: {result}",
        )
        require(path.exists(), f"{view_name}: preview missing: {path}")
        paths.append(str(path))

    return paths, {
        "engine": engine,
        "video_output_api": video_api,
        "views": list(contract["preview"]["views"]),
        "resolution": resolution,
    }


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()
    canonical = load_json(args.canonical_profile)
    constraints = load_json(args.constraint_profile)
    retarget = load_json(args.retarget_profile)
    retarget_axis_contract = load_json(args.retarget_axis_contract)
    grammar_profile = load_json(args.grammar_profile)
    intent_spec = load_json(args.intent_spec)
    static_contract = load_json(args.static_contract)
    visual_contract = load_json(args.visual_contract)
    contract = load_json(args.motion_contract)
    report_path = Path(args.report).resolve()
    preview_dir = Path(args.preview_dir).resolve()

    motion.validate_contract(contract)
    require(canonical["phase"] == "10.6.2", "Requires accepted Phase 10.6.2.")
    require(constraints["phase"] == "10.6.3", "Requires accepted Phase 10.6.3.")
    require(retarget["phase"] == "10.6.6", "Requires accepted Phase 10.6.6.")
    require(static_contract["phase"] == "10.6.7", "Requires accepted Phase 10.6.7.")
    require(visual_contract["phase"] == "10.6.8", "Requires accepted Phase 10.6.8.")
    require(
        retarget["gate"]["orientation_retarget_pass"],
        "Accepted retarget gate is not PASS.",
    )

    source_glb = repo / canonical["source"]["path"]
    require(source_glb.exists(), f"Source GLB missing: {source_glb}")
    require(
        static_core.sha256_file(source_glb) == canonical["source"]["sha256"],
        "Source GLB changed after accepted rig calibration.",
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported = bpy.ops.import_scene.gltf(filepath=str(source_glb))
    require("FINISHED" in imported, f"glTF import failed: {imported}")
    armature = static_core.find_armature(canonical["source"]["armature"])

    if armature.animation_data is not None:
        armature.animation_data_clear()
    for obj in bpy.context.scene.objects:
        if obj.animation_data is not None:
            obj.animation_data_clear()

    runtime = visual_gate.prepare_contact_runtime(
        armature,
        canonical,
        static_contract,
    )
    pose_solver, retarget_solver = (
        static_core.load_ballet_motion_runtime_modules(repo)
    )
    runtime["grammar_profile"] = grammar_profile
    runtime["intent_spec"] = intent_spec
    runtime["pose_solver"] = pose_solver
    runtime["retarget_solver"] = retarget_solver

    roles, hierarchy_evidence = actual_upper_chain(
        armature,
        canonical,
        static_contract,
    )

    start_name = contract["transition"]["start_pose"]
    end_name = contract["transition"]["end_pose"]
    start_pose, start_evidence = realize_endpoint(
        start_name,
        armature,
        canonical,
        constraints,
        retarget,
        retarget_axis_contract,
        static_contract,
        visual_contract,
        runtime,
    )

    lower_names = [
        canonical["canonical_bones"][name]["rig_bone"]
        for name in (
            "pelvis",
            "left_thigh",
            "left_shin",
            "left_foot",
            "left_toes",
            "right_thigh",
            "right_shin",
            "right_foot",
            "right_toes",
        )
    ]
    lower_reference = snapshot_pose_matrices(
        armature,
        lower_names,
    )

    end_pose, end_evidence = realize_endpoint(
        end_name,
        armature,
        canonical,
        constraints,
        retarget,
        retarget_axis_contract,
        static_contract,
        visual_contract,
        runtime,
    )

    moving = set(roles)
    locked = set(start_pose) - moving
    locked_endpoint_error = max(
        matrix_max_error(start_pose[name], end_pose[name])
        for name in locked
    )
    require(
        locked_endpoint_error
        <= float(contract["validation"]["locked_local_matrix_error_max"]),
        "Accepted endpoints differ outside the intended upper-body chain: "
        f"{locked_endpoint_error}.",
    )

    waypoint_pose, waypoint_absolute_bases, waypoint_evidence = (
        realize_rounded_waypoint(
        armature,
        canonical,
        constraints,
        retarget_axis_contract,
        static_contract,
        visual_contract,
        runtime,
        contract,
    )
    )
    motion_cache = prepare_motion_cache(
        armature,
        roles,
        start_pose,
        end_pose,
        waypoint_pose,
        waypoint_absolute_bases,
        contract,
    )
    wrist_cache = prepare_wrist_2dof_cache(
        canonical,
        start_evidence,
        end_evidence,
        motion_cache,
    )

    for name, matrix in start_pose.items():
        armature.pose.bones[name].matrix_basis = matrix.copy()
    bpy.context.view_layer.update()

    frame_start, frame_end, motion_generation = key_motion(
        armature,
        canonical,
        runtime,
        start_pose,
        motion_cache,
        wrist_cache,
        contract,
    )
    diagnostics = validate_motion(
        armature,
        canonical,
        constraints,
        intent_spec,
        visual_contract,
        runtime,
        contract,
        start_pose,
        end_pose,
        roles,
        lower_reference,
        frame_start,
        frame_end,
    )

    preview_paths, preview_evidence = render_previews(
        armature,
        canonical,
        contract,
        preview_dir,
        frame_start,
        frame_end,
    )

    report = {
        "phase": PHASE,
        "contract_id": contract["contract_id"],
        "transition": contract["transition"],
        "authority": contract["authority"],
        "hierarchy": hierarchy_evidence,
        "moving_bones": {
            name: {
                "role": item["role"],
                "endpoint_angle_deg": round(
                    float(item["endpoint_angle_deg"]),
                    8,
                ),
            }
            for name, item in motion_cache.items()
        },
        "endpoint_realization": {
            start_name: start_evidence,
            end_name: end_evidence,
            "locked_endpoint_local_matrix_error": locked_endpoint_error,
        },
        "rounded_transition_waypoint": waypoint_evidence,
        "diagnostics": diagnostics,
        "motion_generation": motion_generation,
        "preview": {
            **preview_evidence,
            "files": preview_paths,
        },
        "automated_gate": {
            "accepted_static_endpoints_reused": True,
            "start_endpoint_exact": True,
            "end_endpoint_exact": True,
            "shoulder_quaternion_shortest_arc": True,
            "parent_aware_elbow_waypoint_path": True,
            "rounded_transition_waypoint_path": True,
            "finger_quaternion_shortest_arc": True,
            "wrist_canonical_2dof_reconstruction": True,
            "minimum_jerk_timing": True,
            "proximal_to_distal_windows": True,
            "no_overshoot_timing": True,
            "lower_body_root_stable": True,
            "hand_centerline_non_crossing": True,
            "elbow_non_inversion": True,
            "wrist_2dof_no_axial_roll": True,
            "semantic_preferred_envelope_proxy": True,
            "quaternion_flip_free": True,
            "glb_exported": False,
        },
        "human_visual_gate": {
            "required": bool(
                contract["preview"]["human_visual_acceptance_required"]
            ),
            "status": "PENDING_REVIEW",
            "question": "Does this look like a dancer moving from bras bas to en avant?",
            "automated_aesthetic_verdict": False,
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("PHASE10_7_1_FOUNDATION_MOTION_AUTOMATED_PROOF=PASS")
    print(f"REPORT={report_path}")
    print(f"PREVIEWS={';'.join(preview_paths)}")
    print("HUMAN_VISUAL_REVIEW=PENDING")
    print("GLB_EXPORT=NOT_PERFORMED")


if __name__ == "__main__":
    main()
