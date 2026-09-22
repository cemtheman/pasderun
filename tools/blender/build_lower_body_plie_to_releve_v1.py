"""Phase 10.8.2 plie -> releve foundation-motion proof."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PHASE = "10.8.2"
HERE = Path(__file__).resolve().parent
REPO_DEFAULT = HERE.parents[1]
BALLET_TOOLS = REPO_DEFAULT / "tools" / "ballet_motion"
for path in (HERE, BALLET_TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402
import render_foundation_pose_visual_gate_v1 as visual_gate  # noqa: E402
import build_lower_body_fifth_to_plie_v1 as base_motion  # noqa: E402
import lower_body_releve_motion as motion  # noqa: E402


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


def contact_state(
    armature: bpy.types.Object,
    runtime: dict,
    mode: str,
) -> dict:
    heights = static_core.contact_heights(
        armature,
        runtime["anchors"],
        runtime["up_axis"],
        float(runtime["sampling"]["low_height_quantile"]),
    )
    proof = static_core.contact_errors(
        mode,
        runtime["rest_heights"],
        heights,
    )
    heel_lifts = {
        side: (
            float(heights[side]["rear"])
            - float(runtime["rest_heights"][side]["rear"])
        )
        for side in ("left", "right")
    }
    return {
        "mode": mode,
        "heights": heights,
        "proof": proof,
        "heel_lifts": heel_lifts,
    }


def solve_intermediate_forefoot_contact(
    armature: bpy.types.Object,
    canonical: dict,
    runtime: dict,
    contract: dict,
) -> dict:
    mode = contract["interpolation"]["intermediate_contact_mode"]
    before = static_core.contact_heights(
        armature,
        runtime["anchors"],
        runtime["up_axis"],
        float(runtime["sampling"]["low_height_quantile"]),
    )
    shift = static_core.root_shift_for_contact(
        mode,
        runtime["rest_heights"],
        before,
    )
    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]
    static_core.set_root_translation_armature_space(
        armature,
        root_name,
        runtime["up_axis"] * float(shift),
    )
    after = contact_state(armature, runtime, mode)
    require(
        after["proof"]["max_abs_error"]
        <= runtime["contact_tolerance"],
        "Intermediate forefoot contact failed: "
        f"{after['proof']['max_abs_error']} > "
        f"{runtime['contact_tolerance']}; "
        f"errors={after['proof']['errors']}.",
    )

    root_translation = base_motion.root_armature_translation(
        armature,
        root_name,
    )
    up = runtime["up_axis"]
    horizontal = root_translation - up * root_translation.dot(up)
    horizontal_error = float(horizontal.length)
    require(
        horizontal_error
        <= float(
            contract["validation"]["root_horizontal_translation_max"]
        ),
        f"Pelvis horizontal drift {horizontal_error} exceeds contract.",
    )
    return {
        "root_up_shift": float(root_translation.dot(up)),
        "root_horizontal_translation": horizontal_error,
        "contact": after["proof"],
        "heel_lifts": after["heel_lifts"],
    }


def set_frame_pose(
    armature: bpy.types.Object,
    start_pose: dict,
    end_pose: dict,
    moving: set[str],
    motion_cache: dict,
    canonical: dict,
    runtime: dict,
    frame: int,
    contract: dict,
) -> dict:
    frame_start = int(contract["transition"]["frame_start"])
    frame_end = motion.frame_end(contract)
    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]

    if frame == frame_start:
        for name, matrix in start_pose.items():
            armature.pose.bones[name].matrix_basis = matrix.copy()
        bpy.context.view_layer.update()
        mode = contract["interpolation"]["start_contact_mode"]
        state = contact_state(armature, runtime, mode)
        require(
            state["proof"]["max_abs_error"]
            <= runtime["contact_tolerance"],
            "Plié start full-foot contact failed.",
        )
        root = base_motion.root_armature_translation(
            armature,
            root_name,
        )
        up = runtime["up_axis"]
        return {
            "frame": frame,
            "progress": 0.0,
            "endpoint_exact": True,
            "contact_mode": mode,
            "root_up_shift": float(root.dot(up)),
            "root_horizontal_translation": float(
                (root - up * root.dot(up)).length
            ),
            "contact": state["proof"],
            "heel_lifts": state["heel_lifts"],
        }

    if frame == frame_end:
        for name, matrix in end_pose.items():
            armature.pose.bones[name].matrix_basis = matrix.copy()
        bpy.context.view_layer.update()
        mode = contract["interpolation"]["end_contact_mode"]
        state = contact_state(armature, runtime, mode)
        require(
            state["proof"]["max_abs_error"]
            <= runtime["contact_tolerance"],
            "Relevé endpoint forefoot contact failed.",
        )
        root = base_motion.root_armature_translation(
            armature,
            root_name,
        )
        up = runtime["up_axis"]
        return {
            "frame": frame,
            "progress": 1.0,
            "endpoint_exact": True,
            "contact_mode": mode,
            "root_up_shift": float(root.dot(up)),
            "root_horizontal_translation": float(
                (root - up * root.dot(up)).length
            ),
            "contact": state["proof"],
            "heel_lifts": state["heel_lifts"],
        }

    p = motion.progress(frame, contract)
    for name, matrix in start_pose.items():
        if name not in moving:
            armature.pose.bones[name].matrix_basis = matrix.copy()

    for rig_name in moving:
        item = motion_cache[rig_name]
        bone = armature.pose.bones[rig_name]
        bone.rotation_mode = "QUATERNION"
        q = item["start_quaternion"].slerp(
            item["end_quaternion"],
            p,
        )
        q.normalize()
        bone.rotation_quaternion = q
        bone.scale = item["scale"].copy()
        if rig_name == root_name:
            bone.location = Vector((0.0, 0.0, 0.0))
        else:
            bone.location = item["start_location"].copy()

    bpy.context.view_layer.update()
    contact = solve_intermediate_forefoot_contact(
        armature,
        canonical,
        runtime,
        contract,
    )
    return {
        "frame": frame,
        "progress": float(p),
        "endpoint_exact": False,
        "contact_mode": contract["interpolation"][
            "intermediate_contact_mode"
        ],
        **contact,
    }


def key_motion(
    armature: bpy.types.Object,
    canonical: dict,
    runtime: dict,
    start_pose: dict,
    end_pose: dict,
    moving: set[str],
    motion_cache: dict,
    contract: dict,
) -> tuple[int, int, dict]:
    frame_start = int(contract["transition"]["frame_start"])
    frame_end = motion.frame_end(contract)

    if armature.animation_data is not None:
        armature.animation_data_clear()

    root_epsilon = float(
        contract["validation"]["root_rise_monotonic_epsilon"]
    )
    heel_epsilon = float(
        contract["validation"]["heel_lift_monotonic_epsilon"]
    )
    scale_limit = float(
        contract["validation"]["moving_scale_error_max"]
    )
    previous_root = None
    previous_heels = {"left": None, "right": None}
    max_scale_error = 0.0
    frames = []

    for frame in range(frame_start, frame_end + 1):
        evidence = set_frame_pose(
            armature,
            start_pose,
            end_pose,
            moving,
            motion_cache,
            canonical,
            runtime,
            frame,
            contract,
        )

        if previous_root is not None:
            require(
                evidence["root_up_shift"]
                >= previous_root - root_epsilon,
                f"Frame {frame}: root rise reversed; "
                f"previous={previous_root}, "
                f"current={evidence['root_up_shift']}.",
            )
        previous_root = evidence["root_up_shift"]

        for side in ("left", "right"):
            prior = previous_heels[side]
            current = float(evidence["heel_lifts"][side])
            if prior is not None:
                require(
                    current >= prior - heel_epsilon,
                    f"Frame {frame}: {side} heel lift reversed; "
                    f"previous={prior}, current={current}.",
                )
            previous_heels[side] = current

        scale_error = 0.0
        if frame not in (frame_start, frame_end):
            for rig_name in moving:
                actual = Vector(armature.pose.bones[rig_name].scale)
                expected = Vector(motion_cache[rig_name]["scale"])
                scale_error = max(
                    scale_error,
                    float((actual - expected).length),
                )
            require(
                scale_error <= scale_limit,
                f"Frame {frame}: scale lock error "
                f"{scale_error} > {scale_limit}.",
            )
            max_scale_error = max(max_scale_error, scale_error)
        evidence["intermediate_scale_lock_error"] = scale_error
        frames.append(evidence)

        for rig_name in moving:
            bone = armature.pose.bones[rig_name]
            bone.keyframe_insert(data_path="location", frame=frame)
            if bone.rotation_mode != "QUATERNION":
                bone.rotation_mode = "QUATERNION"
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
        "method": (
            "ACCEPTED_ENDPOINT_SLERP_PLUS_INTERMEDIATE_"
            "DEFORMED_MESH_FOREFOOT_CONTACT"
        ),
        "intermediate_plantar_toe_search_performed": False,
        "sample_count": len(frames),
        "root_rise_monotone": True,
        "heel_lift_monotone": True,
        "maximum_intermediate_scale_lock_error": max_scale_error,
        "frames": frames,
    }


def validate_motion(
    armature: bpy.types.Object,
    canonical: dict,
    constraints: dict,
    intent_spec: dict,
    runtime: dict,
    contract: dict,
    start_pose: dict,
    end_pose: dict,
    moving: set[str],
    locked: set[str],
    frame_start: int,
    frame_end: int,
) -> dict:
    locked_limit = float(
        contract["validation"]["locked_local_matrix_error_max"]
    )
    endpoint_limit = float(
        contract["validation"]["endpoint_local_matrix_error_max"]
    )
    quat_limit = float(
        contract["validation"]["minimum_consecutive_quaternion_dot"]
    )
    root_epsilon = float(
        contract["validation"]["root_rise_monotonic_epsilon"]
    )
    heel_epsilon = float(
        contract["validation"]["heel_lift_monotonic_epsilon"]
    )
    horizontal_limit = float(
        contract["validation"]["root_horizontal_translation_max"]
    )

    root_name = canonical["canonical_bones"]["pelvis"]["rig_bone"]
    previous_root = None
    previous_heels = {"left": None, "right": None}
    previous_q = {}
    min_q_dot = 1.0
    max_q_step = 0.0
    max_locked_error = 0.0
    max_contact_error = 0.0
    max_horizontal = 0.0
    root_shifts = []
    heel_history = {"left": [], "right": []}
    frames = []

    for frame in range(frame_start, frame_end + 1):
        bpy.context.scene.frame_set(frame)
        bpy.context.view_layer.update()

        locked_error = max(
            (
                base_motion.matrix_max_error(
                    armature.pose.bones[name].matrix_basis,
                    start_pose[name],
                )
                for name in locked
            ),
            default=0.0,
        )
        max_locked_error = max(max_locked_error, locked_error)
        require(
            locked_error <= locked_limit,
            f"Frame {frame}: locked drift "
            f"{locked_error} > {locked_limit}.",
        )

        mode = (
            contract["interpolation"]["start_contact_mode"]
            if frame == frame_start
            else contract["interpolation"]["end_contact_mode"]
            if frame == frame_end
            else contract["interpolation"]["intermediate_contact_mode"]
        )
        contact = contact_state(armature, runtime, mode)
        max_contact_error = max(
            max_contact_error,
            float(contact["proof"]["max_abs_error"]),
        )
        require(
            contact["proof"]["max_abs_error"]
            <= runtime["contact_tolerance"],
            f"Frame {frame}: {mode} contact failed.",
        )

        root = base_motion.root_armature_translation(
            armature,
            root_name,
        )
        up = runtime["up_axis"]
        root_shift = float(root.dot(up))
        horizontal = float(
            (root - up * root.dot(up)).length
        )
        max_horizontal = max(max_horizontal, horizontal)
        require(
            horizontal <= horizontal_limit,
            f"Frame {frame}: root horizontal drift "
            f"{horizontal} > {horizontal_limit}.",
        )
        if previous_root is not None:
            require(
                root_shift >= previous_root - root_epsilon,
                f"Frame {frame}: root rise reversed.",
            )
        previous_root = root_shift
        root_shifts.append(root_shift)

        for side in ("left", "right"):
            heel = float(contact["heel_lifts"][side])
            prior = previous_heels[side]
            if prior is not None:
                require(
                    heel >= prior - heel_epsilon,
                    f"Frame {frame}: {side} heel lift reversed.",
                )
            previous_heels[side] = heel
            heel_history[side].append(heel)

        semantic = motion.semantic_dof_proxy(
            motion.normalized_time(frame, contract),
            contract,
            intent_spec,
            constraints,
        )
        require(
            semantic["status"] == "PASS",
            f"Frame {frame}: preferred semantic envelope failed.",
        )

        for rig_name in moving:
            q = armature.pose.bones[
                rig_name
            ].matrix_basis.to_quaternion()
            q.normalize()
            prior = previous_q.get(rig_name)
            if prior is not None:
                dot = float(prior.dot(q))
                if dot < 0.0:
                    q.negate()
                    dot = float(prior.dot(q))
                min_q_dot = min(min_q_dot, dot)
                require(
                    dot >= quat_limit - 1e-9,
                    f"Frame {frame}: quaternion flip on "
                    f"{rig_name}: {dot}.",
                )
                max_q_step = max(
                    max_q_step,
                    math.degrees(
                        prior.rotation_difference(q).angle
                    ),
                )
            previous_q[rig_name] = q.copy()

        frames.append({
            "frame": frame,
            "normalized_t": round(
                motion.normalized_time(frame, contract),8
            ),
            "progress": round(motion.progress(frame, contract),8),
            "contact_mode": mode,
            "root_up_shift": round(root_shift,8),
            "root_horizontal_translation": round(horizontal,8),
            "heel_lifts": {
                side: round(
                    float(contact["heel_lifts"][side]),8
                )
                for side in ("left","right")
            },
            "contact_max_abs_error": float(
                contact["proof"]["max_abs_error"]
            ),
            "semantic_preferred_envelope_proxy": (
                semantic["status"]
            ),
            "locked_local_matrix_error": locked_error,
        })

    bpy.context.scene.frame_set(frame_start)
    start_error = base_motion.endpoint_error(
        armature,start_pose,moving
    )
    bpy.context.scene.frame_set(frame_end)
    end_error = base_motion.endpoint_error(
        armature,end_pose,moving
    )
    require(
        start_error <= endpoint_limit,
        f"Start endpoint error {start_error} > {endpoint_limit}.",
    )
    require(
        end_error <= endpoint_limit,
        f"End endpoint error {end_error} > {endpoint_limit}.",
    )
    require(
        root_shifts[-1] > root_shifts[0],
        "Relevé endpoint did not rise above plié.",
    )

    minimum_final_lift = (
        float(runtime["metrics"]["foot_chain_length"])
        * float(
            contract["validation"][
                "minimum_final_heel_lift_foot_fraction"
            ]
        )
    )
    for side in ("left","right"):
        require(
            heel_history[side][-1] >= minimum_final_lift,
            f"{side} final heel lift "
            f"{heel_history[side][-1]} < {minimum_final_lift}.",
        )

    return {
        "start_endpoint_local_matrix_error": start_error,
        "end_endpoint_local_matrix_error": end_error,
        "maximum_locked_local_matrix_error": max_locked_error,
        "maximum_contact_error": max_contact_error,
        "contact_tolerance": float(runtime["contact_tolerance"]),
        "maximum_root_horizontal_translation": max_horizontal,
        "root_up_shift_start": root_shifts[0],
        "root_up_shift_end": root_shifts[-1],
        "root_rise": root_shifts[-1]-root_shifts[0],
        "root_rise_monotone": True,
        "heel_lift_monotone": True,
        "heel_lift_start": {
            side: heel_history[side][0]
            for side in ("left","right")
        },
        "heel_lift_end": {
            side: heel_history[side][-1]
            for side in ("left","right")
        },
        "minimum_final_heel_lift": minimum_final_lift,
        "minimum_consecutive_quaternion_dot": min_q_dot,
        "maximum_consecutive_quaternion_step_deg": max_q_step,
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
    engine = visual_gate.configure_workbench(
        scene,
        resolution,
    )
    video_api = base_motion.configure_video_output(scene)

    scene.frame_start = frame_start
    scene.frame_end = frame_end
    scene.render.fps = int(contract["transition"]["fps"])
    scene.render.ffmpeg.format = contract["preview"]["container"]
    scene.render.ffmpeg.codec = contract["preview"]["codec"]
    scene.render.ffmpeg.constant_rate_factor = "MEDIUM"

    scene.frame_set(frame_start)
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
            f"plie_to_releve_{view_name.lower()}.mp4"
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
    retarget_axis_contract = load_json(
        args.retarget_axis_contract
    )
    grammar_profile = load_json(args.grammar_profile)
    intent_spec = load_json(args.intent_spec)
    static_contract = load_json(args.static_contract)
    visual_contract = load_json(args.visual_contract)
    contract = load_json(args.motion_contract)
    report_path = Path(args.report).resolve()
    preview_dir = Path(args.preview_dir).resolve()

    motion.validate_contract(contract)
    require(canonical["phase"]=="10.6.2","Requires 10.6.2.")
    require(constraints["phase"]=="10.6.3","Requires 10.6.3.")
    require(retarget["phase"]=="10.6.6","Requires 10.6.6.")
    require(static_contract["phase"]=="10.6.7","Requires 10.6.7.")
    require(visual_contract["phase"]=="10.6.8","Requires 10.6.8.")
    require(
        retarget["gate"]["orientation_retarget_pass"],
        "Accepted retarget gate is not PASS.",
    )

    source_glb=repo/canonical["source"]["path"]
    require(source_glb.exists(),f"Source GLB missing: {source_glb}")
    require(
        static_core.sha256_file(source_glb)
        == canonical["source"]["sha256"],
        "Source GLB changed after accepted calibration.",
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported=bpy.ops.import_scene.gltf(filepath=str(source_glb))
    require("FINISHED" in imported,f"glTF import failed: {imported}")
    armature=static_core.find_armature(
        canonical["source"]["armature"]
    )

    if armature.animation_data is not None:
        armature.animation_data_clear()
    for obj in bpy.context.scene.objects:
        if obj.animation_data is not None:
            obj.animation_data_clear()

    runtime=visual_gate.prepare_contact_runtime(
        armature,canonical,static_contract
    )
    pose_solver,retarget_solver=(
        static_core.load_ballet_motion_runtime_modules(repo)
    )
    runtime["grammar_profile"]=grammar_profile
    runtime["intent_spec"]=intent_spec
    runtime["pose_solver"]=pose_solver
    runtime["retarget_solver"]=retarget_solver

    start_name=contract["transition"]["start_pose"]
    end_name=contract["transition"]["end_pose"]
    start_pose,start_evidence=base_motion.realize_endpoint(
        start_name,armature,canonical,constraints,retarget,
        retarget_axis_contract,static_contract,runtime
    )
    end_pose,end_evidence=base_motion.realize_endpoint(
        end_name,armature,canonical,constraints,retarget,
        retarget_axis_contract,static_contract,runtime
    )

    moving,locked,partition=base_motion.endpoint_partition(
        armature,start_pose,end_pose,canonical,contract
    )
    root_name=canonical["canonical_bones"]["pelvis"]["rig_bone"]
    require(
        root_name in moving,
        "Pelvis must participate in plié -> relevé motion.",
    )
    motion_cache=base_motion.prepare_motion_cache(
        start_pose,end_pose,moving,root_name,contract
    )

    for name,matrix in start_pose.items():
        armature.pose.bones[name].matrix_basis=matrix.copy()
    bpy.context.view_layer.update()

    frame_start,frame_end,generation=key_motion(
        armature,canonical,runtime,start_pose,end_pose,
        moving,motion_cache,contract
    )
    diagnostics=validate_motion(
        armature,canonical,constraints,intent_spec,runtime,
        contract,start_pose,end_pose,moving,locked,
        frame_start,frame_end
    )
    preview_paths,preview_evidence=render_previews(
        armature,canonical,contract,preview_dir,
        frame_start,frame_end
    )

    report={
        "phase":PHASE,
        "contract_id":contract["contract_id"],
        "transition":contract["transition"],
        "authority":contract["authority"],
        "endpoint_realization":{
            start_name:start_evidence,
            end_name:end_evidence,
        },
        "endpoint_partition":partition,
        "moving_bones":{
            name:{
                "endpoint_angle_deg":round(
                    float(item["endpoint_angle_deg"]),8
                ),
                "translation_error":float(
                    item["translation_error"]
                ),
                "accepted_endpoint_decomposition_scale_noise":float(
                    item["scale_error"]
                ),
            }
            for name,item in motion_cache.items()
        },
        "motion_generation":generation,
        "diagnostics":diagnostics,
        "preview":{
            **preview_evidence,
            "files":preview_paths,
        },
        "automated_gate":{
            "accepted_static_endpoints_reused":True,
            "start_endpoint_exact":True,
            "end_endpoint_exact":True,
            "phase10_6_endpoint_motion_authority":True,
            "accepted_trunk_hierarchy_motion":True,
            "quaternion_shortest_arc":True,
            "accepted_endpoint_decomposition_noise_bounded":True,
            "intermediate_scale_locked":True,
            "minimum_jerk_timing":True,
            "start_full_foot_contact":True,
            "intermediate_forefoot_contact":True,
            "end_forefoot_contact":True,
            "root_rise_monotone":True,
            "heel_lift_monotone":True,
            "meaningful_final_heel_lift":True,
            "root_horizontal_drift_blocked":True,
            "nonparticipating_bones_stable":True,
            "semantic_preferred_envelope_proxy":True,
            "quaternion_flip_free":True,
            "intermediate_plantar_toe_search_absent":True,
            "glb_exported":False,
        },
        "human_visual_gate":{
            "required":bool(
                contract["preview"][
                    "human_visual_acceptance_required"
                ]
            ),
            "status":"PENDING_REVIEW",
            "question":(
                "Does plie to releve read as coordinated straightening "
                "and rise onto the forefoot, with heels lifting together "
                "and no foot slide or toe pop?"
            ),
            "automated_aesthetic_verdict":False,
        },
    }

    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(
        json.dumps(report,indent=2),
        encoding="utf-8",
    )

    print("PHASE10_8_2_RELEVE_MOTION_AUTOMATED_PROOF=PASS")
    print(f"REPORT={report_path}")
    print(f"PREVIEWS={';'.join(preview_paths)}")
    print("HUMAN_VISUAL_REVIEW=PENDING")
    print("GLB_EXPORT=NOT_PERFORMED")


if __name__=="__main__":
    main()
