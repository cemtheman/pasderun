"""Phase 10.10.1 coordinated accepted foundation-motion proof."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import bpy


PHASE = "10.10.1"
HERE = Path(__file__).resolve().parent
REPO_DEFAULT = HERE.parents[1]
BALLET_TOOLS = REPO_DEFAULT / "tools" / "ballet_motion"
for path in (HERE, BALLET_TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402
import render_foundation_pose_visual_gate_v1 as visual_gate  # noqa: E402
import build_foundation_transition_v1 as arm_a  # noqa: E402
import build_foundation_transition_en_avant_to_second_v1 as arm_b  # noqa: E402
import build_lower_body_fifth_to_plie_v1 as lower_a  # noqa: E402
import build_lower_body_plie_to_releve_v1 as lower_b  # noqa: E402
import coordinated_foundation_motion as coordinated  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--canonical-profile", required=True)
    p.add_argument("--constraint-profile", required=True)
    p.add_argument("--retarget-profile", required=True)
    p.add_argument("--retarget-axis-contract", required=True)
    p.add_argument("--grammar-profile", required=True)
    p.add_argument("--intent-spec", required=True)
    p.add_argument("--static-contract", required=True)
    p.add_argument("--visual-contract", required=True)
    p.add_argument("--arm-contract-a", required=True)
    p.add_argument("--arm-contract-b", required=True)
    p.add_argument("--lower-contract-a", required=True)
    p.add_argument("--lower-contract-b", required=True)
    p.add_argument("--coordinated-contract", required=True)
    p.add_argument("--report", required=True)
    p.add_argument("--preview-dir", required=True)
    return p.parse_args(sys.argv[sys.argv.index("--") + 1:])


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def make_segment_contract(source: dict, frame_start: int) -> dict:
    result = copy.deepcopy(source)
    result["transition"]["frame_start"] = int(frame_start)
    return result


def max_pose_error(a: dict, b: dict, names: set[str]) -> float:
    return max(
        (
            lower_a.matrix_max_error(a[name], b[name])
            for name in names
        ),
        default=0.0,
    )


def snapshot_local(
    armature: bpy.types.Object,
    names: set[str],
) -> dict:
    return {
        name: armature.pose.bones[name].matrix_basis.copy()
        for name in names
    }


def restore_local(
    armature: bpy.types.Object,
    matrices: dict,
) -> None:
    for name, matrix in matrices.items():
        armature.pose.bones[name].matrix_basis = matrix.copy()
    bpy.context.view_layer.update()


def prepare_arm_segment(
    module,
    armature,
    canonical,
    static_contract,
    start_pose,
    start_evidence,
    end_pose,
    end_evidence,
    contract,
) -> tuple[dict, dict, dict]:
    roles, hierarchy = module.actual_upper_chain(
        armature,
        canonical,
        static_contract,
    )
    cache = module.prepare_motion_cache(
        armature,
        roles,
        start_pose,
        end_pose,
        contract,
    )
    wrists = module.prepare_wrist_2dof_cache(
        canonical,
        start_evidence,
        end_evidence,
        cache,
    )
    return roles, cache, {
        "wrist_cache": wrists,
        "hierarchy": hierarchy,
    }


def apply_arm_overlay(
    module,
    armature,
    canonical,
    runtime,
    start_pose,
    roles,
    cache,
    wrist_cache,
    contract,
    frame,
) -> dict:
    arm_names = set(roles)
    preserved = {
        bone.name: bone.matrix_basis.copy()
        for bone in armature.pose.bones
        if bone.name not in arm_names
    }

    trace = module.set_interpolated_pose(
        armature,
        start_pose,
        cache,
        frame,
        contract,
    )

    # Source arm primitive resets non-arm bones to its static start pose.
    # Restore the already-solved lower/trunk authority, retaining only the
    # accepted arm-chain local transforms from the source primitive.
    restore_local(armature, preserved)

    frame_start = int(contract["transition"]["frame_start"])
    frame_end = module.motion.frame_end(contract)
    wrist = module.apply_wrist_2dof_interpolation(
        armature,
        canonical,
        cache,
        wrist_cache,
        trace,
        frame,
        frame_start,
        frame_end,
    )
    clearance = module.enforce_hand_centerline_clearance(
        armature,
        canonical,
        runtime,
        contract,
        cache,
        frame,
        frame_start,
        frame_end,
    )
    bpy.context.view_layer.update()

    return {
        "trace": trace,
        "wrist": wrist,
        "clearance": clearance,
    }


def key_combined_pose(
    armature: bpy.types.Object,
    names: set[str],
    frame: int,
) -> None:
    for name in names:
        bone = armature.pose.bones[name]
        bone.keyframe_insert(data_path="location", frame=frame)
        if bone.rotation_mode != "QUATERNION":
            bone.rotation_mode = "QUATERNION"
        bone.keyframe_insert(
            data_path="rotation_quaternion",
            frame=frame,
        )
        bone.keyframe_insert(data_path="scale", frame=frame)


def post_overlay_contact(
    armature,
    runtime,
    static_contract,
    frame,
    boundary,
) -> dict:
    if frame <= boundary:
        state = lower_a.contact_state(
            armature,
            runtime,
            static_contract,
        )
        mode = "SOLVE_FULL_FOOT_CONTACT"
        heels = {
            side: float(
                state["heights"][side]["rear"]
                - runtime["rest_heights"][side]["rear"]
            )
            for side in ("left", "right")
        }
    else:
        state = lower_b.contact_state(
            armature,
            runtime,
            "SOLVE_FOREFOOT_CONTACT",
        )
        mode = "SOLVE_FOREFOOT_CONTACT"
        heels = {
            side: float(state["heel_lifts"][side])
            for side in ("left", "right")
        }

    require(
        state["proof"]["max_abs_error"]
        <= runtime["contact_tolerance"],
        f"Frame {frame}: post-overlay {mode} contact failed: "
        f"{state['proof']['max_abs_error']} > "
        f"{runtime['contact_tolerance']}.",
    )
    return {
        "mode": mode,
        "proof": state["proof"],
        "heel_lifts": heels,
    }


def render_previews(
    armature,
    canonical,
    contract,
    preview_dir: Path,
) -> tuple[list[str], dict]:
    preview_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    resolution = int(contract["preview"]["resolution"])
    engine = visual_gate.configure_workbench(scene, resolution)
    video_api = arm_a.configure_video_output(scene)

    scene.frame_start = int(contract["timeline"]["frame_start"])
    scene.frame_end = int(contract["timeline"]["frame_end"])
    scene.render.fps = int(contract["timeline"]["fps"])
    scene.render.ffmpeg.format = contract["preview"]["container"]
    scene.render.ffmpeg.codec = contract["preview"]["codec"]
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"

    scene.frame_set(scene.frame_start)
    camera, center_world, height = visual_gate.create_camera(
        armature,
        canonical,
    )

    files = []
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
            f"coordinated_foundation_{view_name.lower()}.mp4"
        )
        if path.exists():
            path.unlink()
        scene.render.filepath = str(path)
        result = bpy.ops.render.render(animation=True)
        require(
            "FINISHED" in result,
            f"{view_name}: preview render failed: {result}",
        )
        require(
            path.exists(),
            f"{view_name}: preview missing: {path}",
        )
        files.append(str(path))

    return files, {
        "engine": engine,
        "video_output_api": video_api,
        "views": list(contract["preview"]["views"]),
        "resolution": resolution,
    }


def validate_animation(
    armature,
    canonical,
    runtime,
    static_contract,
    contract,
    arm_names,
    lower_owned_names,
    arm_boundary_pose,
    lower_boundary_pose,
    combined_names,
) -> dict:
    scene = bpy.context.scene
    start = int(contract["timeline"]["frame_start"])
    boundary = int(contract["timeline"]["shared_boundary_frame"])
    end = int(contract["timeline"]["frame_end"])

    q_limit = float(
        contract["validation"]["minimum_consecutive_quaternion_dot"]
    )
    horizontal_limit = float(
        contract["validation"]["root_horizontal_translation_max"]
    )
    descent_epsilon = float(
        contract["validation"]["root_descent_monotonic_epsilon"]
    )
    rise_epsilon = float(
        contract["validation"]["root_rise_monotonic_epsilon"]
    )
    heel_epsilon = float(
        contract["validation"]["heel_lift_monotonic_epsilon"]
    )

    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]
    previous_q = {}
    min_dot = 1.0
    max_step = 0.0
    root_shifts = []
    heels = {"left": [], "right": []}
    max_contact = 0.0
    max_horizontal = 0.0
    boundary_steps = {}
    rows = []

    for frame in range(start, end + 1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        contact = post_overlay_contact(
            armature,
            runtime,
            static_contract,
            frame,
            boundary,
        )
        max_contact = max(
            max_contact,
            float(contact["proof"]["max_abs_error"]),
        )

        root = lower_a.root_armature_translation(
            armature,
            root_name,
        )
        up = runtime["up_axis"]
        shift = float(root.dot(up))
        horizontal = float(
            (root - up * root.dot(up)).length
        )
        require(
            horizontal <= horizontal_limit,
            f"Frame {frame}: root horizontal drift "
            f"{horizontal} > {horizontal_limit}.",
        )
        max_horizontal = max(max_horizontal, horizontal)
        root_shifts.append(shift)

        for side in ("left", "right"):
            heels[side].append(
                float(contact["heel_lifts"][side])
            )

        frame_step = 0.0
        for name in combined_names:
            q = armature.pose.bones[
                name
            ].matrix_basis.to_quaternion()
            q.normalize()
            prior = previous_q.get(name)
            if prior is not None:
                dot = float(prior.dot(q))
                if dot < 0.0:
                    q.negate()
                    dot = float(prior.dot(q))
                min_dot = min(min_dot, dot)
                require(
                    dot >= q_limit - 1e-9,
                    f"Frame {frame}: quaternion flip on {name}: {dot}.",
                )
                step = math.degrees(
                    prior.rotation_difference(q).angle
                )
                frame_step = max(frame_step, step)
                max_step = max(max_step, step)
            previous_q[name] = q.copy()

        if frame in (boundary - 1, boundary, boundary + 1):
            boundary_steps[str(frame)] = frame_step

        rows.append({
            "frame": frame,
            "contact_mode": contact["mode"],
            "contact_max_abs_error": float(
                contact["proof"]["max_abs_error"]
            ),
            "root_up_shift": shift,
            "root_horizontal_translation": horizontal,
            "heel_lifts": contact["heel_lifts"],
            "maximum_combined_step_deg": frame_step,
        })

    for index in range(1, boundary):
        require(
            root_shifts[index]
            <= root_shifts[index - 1] + descent_epsilon,
            f"Frame {index + 1}: coordinated descent reversed.",
        )

    for index in range(boundary, len(root_shifts)):
        require(
            root_shifts[index]
            >= root_shifts[index - 1] - rise_epsilon,
            f"Frame {index + 1}: coordinated rise reversed.",
        )
        for side in ("left", "right"):
            require(
                heels[side][index]
                >= heels[side][index - 1] - heel_epsilon,
                f"Frame {index + 1}: {side} heel lift reversed.",
            )

    scene.frame_set(boundary)
    actual = {
        name: armature.pose.bones[name].matrix_basis.copy()
        for name in set(arm_names) | set(lower_owned_names)
    }
    arm_error = max_pose_error(
        actual,
        arm_boundary_pose,
        set(arm_names),
    )
    lower_error = max_pose_error(
        actual,
        lower_boundary_pose,
        set(lower_owned_names),
    )

    require(
        arm_error
        <= float(
            contract["validation"][
                "shared_arm_boundary_local_matrix_error_max"
            ]
        ),
        f"Coordinated arm boundary error {arm_error}.",
    )
    require(
        lower_error
        <= float(
            contract["validation"][
                "shared_lower_boundary_local_matrix_error_max"
            ]
        ),
        f"Coordinated lower boundary error {lower_error}.",
    )

    return {
        "sample_count": len(rows),
        "sampled_every_frame": True,
        "maximum_post_overlay_contact_error": max_contact,
        "contact_tolerance": float(runtime["contact_tolerance"]),
        "maximum_root_horizontal_translation": max_horizontal,
        "root_up_shift_start": root_shifts[0],
        "root_up_shift_boundary": root_shifts[boundary - 1],
        "root_up_shift_end": root_shifts[-1],
        "root_descent": root_shifts[0] - root_shifts[boundary - 1],
        "root_rise": root_shifts[-1] - root_shifts[boundary - 1],
        "root_descent_monotone": True,
        "root_rise_monotone": True,
        "heel_lift_monotone_after_boundary": True,
        "heel_lift_end": {
            side: heels[side][-1]
            for side in ("left", "right")
        },
        "minimum_consecutive_quaternion_dot": min_dot,
        "maximum_consecutive_combined_step_deg": max_step,
        "arm_boundary_local_matrix_error": arm_error,
        "lower_boundary_local_matrix_error": lower_error,
        "boundary_step_diagnostics_deg": boundary_steps,
        "frames": rows,
    }


def main() -> None:
    args = parse_args()
    repo = Path(args.repo).resolve()

    canonical = load_json(args.canonical_profile)
    constraints = load_json(args.constraint_profile)
    retarget = load_json(args.retarget_profile)
    axis_contract = load_json(args.retarget_axis_contract)
    grammar = load_json(args.grammar_profile)
    intents = load_json(args.intent_spec)
    static_contract = load_json(args.static_contract)
    visual_contract = load_json(args.visual_contract)
    arm_contract_a = load_json(args.arm_contract_a)
    arm_contract_b = load_json(args.arm_contract_b)
    lower_contract_a = load_json(args.lower_contract_a)
    lower_contract_b = load_json(args.lower_contract_b)
    contract = load_json(args.coordinated_contract)

    report_path = Path(args.report).resolve()
    preview_dir = Path(args.preview_dir).resolve()

    coordinated.validate_contract(contract)
    arm_a.motion.validate_contract(arm_contract_a)
    arm_b.motion.validate_contract(arm_contract_b)
    lower_a.motion.validate_contract(lower_contract_a)
    lower_b.motion.validate_contract(lower_contract_b)

    source_glb = repo / canonical["source"]["path"]
    require(source_glb.exists(), f"Source GLB missing: {source_glb}")
    require(
        static_core.sha256_file(source_glb)
        == canonical["source"]["sha256"],
        "Source GLB changed after accepted calibration.",
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported = bpy.ops.import_scene.gltf(filepath=str(source_glb))
    require("FINISHED" in imported, f"glTF import failed: {imported}")
    armature = static_core.find_armature(
        canonical["source"]["armature"]
    )

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
    runtime["grammar_profile"] = grammar
    runtime["intent_spec"] = intents
    runtime["pose_solver"] = pose_solver
    runtime["retarget_solver"] = retarget_solver

    # Accepted arm endpoints.
    arm_start, arm_start_e = arm_a.realize_endpoint(
        "bras_bas", armature, canonical, constraints, retarget,
        axis_contract, static_contract, visual_contract, runtime
    )
    arm_boundary_a, arm_boundary_a_e = arm_a.realize_endpoint(
        "en_avant", armature, canonical, constraints, retarget,
        axis_contract, static_contract, visual_contract, runtime
    )
    arm_boundary_b, arm_boundary_b_e = arm_b.realize_endpoint(
        "en_avant", armature, canonical, constraints, retarget,
        axis_contract, static_contract, visual_contract, runtime
    )
    arm_end, arm_end_e = arm_b.realize_endpoint(
        "second", armature, canonical, constraints, retarget,
        axis_contract, static_contract, visual_contract, runtime
    )

    # Accepted lower endpoints.
    lower_start, _ = lower_a.realize_endpoint(
        "fifth", armature, canonical, constraints, retarget,
        axis_contract, static_contract, runtime
    )
    lower_boundary_a, _ = lower_a.realize_endpoint(
        "plie", armature, canonical, constraints, retarget,
        axis_contract, static_contract, runtime
    )
    lower_boundary_b, _ = lower_a.realize_endpoint(
        "plie", armature, canonical, constraints, retarget,
        axis_contract, static_contract, runtime
    )
    lower_end, _ = lower_a.realize_endpoint(
        "releve", armature, canonical, constraints, retarget,
        axis_contract, static_contract, runtime
    )

    arm_roles_a, hierarchy_a = arm_a.actual_upper_chain(
        armature, canonical, static_contract
    )
    arm_roles_b, hierarchy_b = arm_b.actual_upper_chain(
        armature, canonical, static_contract
    )
    require(
        arm_roles_a == arm_roles_b,
        "Accepted arm role maps differ.",
    )
    arm_names = set(arm_roles_a)

    seg_arm_a = make_segment_contract(arm_contract_a, 1)
    seg_arm_b = make_segment_contract(arm_contract_b, 61)
    seg_lower_a = make_segment_contract(lower_contract_a, 1)
    seg_lower_b = make_segment_contract(lower_contract_b, 61)

    arm_boundary_error = max_pose_error(
        arm_boundary_a,
        arm_boundary_b,
        arm_names,
    )
    require(
        arm_boundary_error
        <= float(
            contract["validation"][
                "shared_arm_boundary_local_matrix_error_max"
            ]
        ),
        f"Accepted arm en_avant mismatch: {arm_boundary_error}.",
    )

    lower_shared_names = set(lower_boundary_a) & set(lower_boundary_b)
    lower_boundary_error = max_pose_error(
        lower_boundary_a,
        lower_boundary_b,
        lower_shared_names,
    )
    require(
        lower_boundary_error
        <= float(
            contract["validation"][
                "shared_lower_boundary_local_matrix_error_max"
            ]
        ),
        f"Accepted lower plié mismatch: {lower_boundary_error}.",
    )

    moving_lower_a, _, partition_a = lower_a.endpoint_partition(
        armature,
        lower_start,
        lower_boundary_a,
        canonical,
        seg_lower_a,
    )
    moving_lower_b, _, partition_b = lower_a.endpoint_partition(
        armature,
        lower_boundary_b,
        lower_end,
        canonical,
        seg_lower_b,
    )
    lower_moving = set(moving_lower_a) | set(moving_lower_b)
    lower_semantic = (
        set(partition_a["semantic_driver_rig_bones"])
        | set(partition_b["semantic_driver_rig_bones"])
    )
    lower_followers = (
        set(partition_a["hierarchy_follower_rig_bones"])
        | set(partition_b["hierarchy_follower_rig_bones"])
    )

    overlap = arm_names & lower_moving
    semantic_overlap = arm_names & lower_semantic
    illegal_overlap = overlap - lower_followers

    require(
        len(semantic_overlap)
        <= int(
            contract["validation"][
                "arm_lower_semantic_overlap_count_max"
            ]
        ),
        "Arm chain overlaps lower semantic drivers: "
        + ", ".join(sorted(semantic_overlap)),
    )
    require(
        not illegal_overlap,
        "Arm/lower overlap is not hierarchy-follower-only: "
        + ", ".join(sorted(illegal_overlap)),
    )

    lower_owned = lower_moving - arm_names
    combined_names = lower_moving | arm_names

    arm_cache_a = arm_a.prepare_motion_cache(
        armature,
        arm_roles_a,
        arm_start,
        arm_boundary_a,
        seg_arm_a,
    )
    arm_wrist_a = arm_a.prepare_wrist_2dof_cache(
        canonical,
        arm_start_e,
        arm_boundary_a_e,
        arm_cache_a,
    )
    arm_cache_b = arm_b.prepare_motion_cache(
        armature,
        arm_roles_b,
        arm_boundary_b,
        arm_end,
        seg_arm_b,
    )
    arm_wrist_b = arm_b.prepare_wrist_2dof_cache(
        canonical,
        arm_boundary_b_e,
        arm_end_e,
        arm_cache_b,
    )

    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]
    lower_cache_a = lower_a.prepare_motion_cache(
        lower_start,
        lower_boundary_a,
        moving_lower_a,
        root_name,
        seg_lower_a,
    )
    lower_cache_b = lower_b.prepare_motion_cache(
        lower_boundary_b,
        lower_end,
        moving_lower_b,
        root_name,
        seg_lower_b,
    )

    # Generate one coordinated pose per frame and key it exactly once.
    generation = []
    boundary = int(contract["timeline"]["shared_boundary_frame"])
    for frame in range(1, 122):
        if frame <= boundary:
            lower_evidence = lower_a.set_frame_pose(
                armature,
                lower_start,
                lower_boundary_a,
                moving_lower_a,
                lower_cache_a,
                canonical,
                runtime,
                static_contract,
                frame,
                seg_lower_a,
            )
            arm_evidence = apply_arm_overlay(
                arm_a,
                armature,
                canonical,
                runtime,
                arm_start,
                arm_roles_a,
                arm_cache_a,
                arm_wrist_a,
                seg_arm_a,
                frame,
            )
        else:
            lower_evidence = lower_b.set_frame_pose(
                armature,
                lower_boundary_b,
                lower_end,
                moving_lower_b,
                lower_cache_b,
                canonical,
                runtime,
                frame,
                seg_lower_b,
            )
            arm_evidence = apply_arm_overlay(
                arm_b,
                armature,
                canonical,
                runtime,
                arm_boundary_b,
                arm_roles_b,
                arm_cache_b,
                arm_wrist_b,
                seg_arm_b,
                frame,
            )

        contact = post_overlay_contact(
            armature,
            runtime,
            static_contract,
            frame,
            boundary,
        )
        key_combined_pose(
            armature,
            combined_names,
            frame,
        )
        generation.append({
            "frame": frame,
            "lower": lower_evidence,
            "arm": arm_evidence,
            "post_overlay_contact": {
                "mode": contact["mode"],
                "max_abs_error": float(
                    contact["proof"]["max_abs_error"]
                ),
                "heel_lifts": contact["heel_lifts"],
            },
        })

    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 121
    scene.render.fps = 30
    scene.frame_set(1)

    diagnostics = validate_animation(
        armature,
        canonical,
        runtime,
        static_contract,
        contract,
        arm_names,
        lower_owned,
        arm_boundary_a,
        lower_boundary_a,
        combined_names,
    )

    previews, preview_evidence = render_previews(
        armature,
        canonical,
        contract,
        preview_dir,
    )

    report = {
        "phase": PHASE,
        "contract_id": contract["contract_id"],
        "authority_partition": {
            "arm_explicit_rig_bones": sorted(arm_names),
            "lower_semantic_driver_rig_bones": sorted(lower_semantic),
            "lower_hierarchy_follower_rig_bones": sorted(lower_followers),
            "lower_moving_rig_bones": sorted(lower_moving),
            "arm_lower_overlap_rig_bones": sorted(overlap),
            "arm_lower_semantic_overlap_rig_bones": sorted(
                semantic_overlap
            ),
            "arm_override_lower_hierarchy_follower_rig_bones": sorted(
                overlap
            ),
            "lower_owned_rig_bones": sorted(lower_owned),
            "overlap_policy": contract["authority"]["overlap_policy"],
        },
        "source_boundaries": {
            "arm_en_avant_error": arm_boundary_error,
            "lower_plie_error": lower_boundary_error,
        },
        "source_hierarchies": {
            "arm_a": hierarchy_a,
            "arm_b": hierarchy_b,
            "lower_a": partition_a,
            "lower_b": partition_b,
        },
        "generation": {
            "sample_count": len(generation),
            "single_key_authority_per_frame": True,
            "source_primitive_math_reimplemented": False,
        },
        "diagnostics": diagnostics,
        "preview": {
            **preview_evidence,
            "files": previews,
        },
        "automated_gate": {
            "arm_source_primitives_reused": True,
            "lower_source_primitives_reused": True,
            "authority_overlap_explicit": True,
            "arm_lower_semantic_overlap_absent": True,
            "overlap_limited_to_lower_hierarchy_followers": True,
            "arm_explicit_override_policy_applied": True,
            "root_contact_owned_by_lower_solver": True,
            "post_overlay_contact_pass": True,
            "arm_boundary_pass": True,
            "lower_boundary_pass": True,
            "root_descent_monotone": True,
            "root_rise_monotone": True,
            "heel_lift_monotone_after_boundary": True,
            "quaternion_flip_free": True,
            "sampled_every_frame": True,
            "single_humanoid_motion_authority": True,
            "primitive_math_reimplementation_absent": True,
            "glb_exported": False,
        },
        "human_visual_gate": {
            "required": True,
            "status": "PENDING_REVIEW",
            "question": (
                "Does the simultaneous arm and lower-body foundation phrase "
                "read as one coordinated ballet action, with clean port de "
                "bras, plié/relevé weight logic, no authority snap at frame "
                "61, and no arm/trunk or foot-contact artifact?"
            ),
            "automated_aesthetic_verdict": False,
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("PHASE10_10_1_COORDINATED_FOUNDATION_AUTOMATED_PROOF=PASS")
    print(f"REPORT={report_path}")
    print(f"PREVIEWS={';'.join(previews)}")
    print("HUMAN_VISUAL_REVIEW=PENDING")
    print("GLB_EXPORT=NOT_PERFORMED")


if __name__ == "__main__":
    main()
