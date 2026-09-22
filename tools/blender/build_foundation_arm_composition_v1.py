"""Phase 10.9.1 accepted arm-primitive composition proof."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import bpy


PHASE="10.9.1"
HERE=Path(__file__).resolve().parent
REPO_DEFAULT=HERE.parents[1]
BALLET_TOOLS=REPO_DEFAULT/"tools"/"ballet_motion"
for path in (HERE,BALLET_TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402
import render_foundation_pose_visual_gate_v1 as visual_gate  # noqa: E402
import build_foundation_transition_v1 as arm_a  # noqa: E402
import build_foundation_transition_en_avant_to_second_v1 as arm_b  # noqa: E402
import foundation_motion_composition as composition  # noqa: E402


def parse_args() -> argparse.Namespace:
    p=argparse.ArgumentParser()
    p.add_argument("--repo",required=True)
    p.add_argument("--canonical-profile",required=True)
    p.add_argument("--constraint-profile",required=True)
    p.add_argument("--retarget-profile",required=True)
    p.add_argument("--retarget-axis-contract",required=True)
    p.add_argument("--grammar-profile",required=True)
    p.add_argument("--intent-spec",required=True)
    p.add_argument("--static-contract",required=True)
    p.add_argument("--visual-contract",required=True)
    p.add_argument("--source-contract-a",required=True)
    p.add_argument("--source-contract-b",required=True)
    p.add_argument("--composition-contract",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--preview-dir",required=True)
    return p.parse_args(sys.argv[sys.argv.index("--")+1:])


def require(condition: bool,message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def max_pose_error(a: dict,b: dict,names=None) -> float:
    selected=names if names is not None else set(a)&set(b)
    return max(
        (arm_a.matrix_max_error(a[name],b[name]) for name in selected),
        default=0.0,
    )


def make_segment_contract(source: dict,frame_start: int) -> dict:
    result=copy.deepcopy(source)
    result["transition"]["frame_start"]=int(frame_start)
    return result


def realize(
    module,
    pose_name,
    armature,
    canonical,
    constraints,
    retarget,
    axis_contract,
    static_contract,
    visual_contract,
    runtime,
):
    return module.realize_endpoint(
        pose_name,
        armature,
        canonical,
        constraints,
        retarget,
        axis_contract,
        static_contract,
        visual_contract,
        runtime,
    )


def canonicalize_locked_endpoint(
    module,
    start_pose: dict,
    end_pose: dict,
    moving: set[str],
    contract: dict,
) -> dict:
    locked=set(start_pose)-moving
    raw=max(
        (
            module.matrix_max_error(start_pose[name],end_pose[name])
            for name in locked
        ),
        default=0.0,
    )
    ceiling=float(
        contract["validation"].get(
            "accepted_endpoint_locked_noise_max",
            contract["validation"]["locked_local_matrix_error_max"],
        )
    )
    require(
        raw <= ceiling,
        f"{contract['phase']}: locked endpoint difference "
        f"{raw} > {ceiling}.",
    )
    for name in locked:
        end_pose[name]=start_pose[name].copy()
    return {
        "locked_count":len(locked),
        "raw_locked_endpoint_error":raw,
        "canonicalized_locked_endpoint_error":max(
            (
                module.matrix_max_error(start_pose[name],end_pose[name])
                for name in locked
            ),
            default=0.0,
        ),
    }


def apply_segment_frame(
    module,
    armature,
    canonical,
    runtime,
    start_pose,
    motion_cache,
    wrist_cache,
    contract,
    frame,
) -> dict:
    frame_start=int(contract["transition"]["frame_start"])
    frame_end=module.motion.frame_end(contract)
    trace=module.set_interpolated_pose(
        armature,
        start_pose,
        motion_cache,
        frame,
        contract,
    )
    wrist=module.apply_wrist_2dof_interpolation(
        armature,
        canonical,
        motion_cache,
        wrist_cache,
        trace,
        frame,
        frame_start,
        frame_end,
    )
    clearance=module.enforce_hand_centerline_clearance(
        armature,
        canonical,
        runtime,
        contract,
        motion_cache,
        frame,
        frame_start,
        frame_end,
    )
    for rig_name in motion_cache:
        bone=armature.pose.bones[rig_name]
        bone.keyframe_insert(data_path="location",frame=frame)
        bone.keyframe_insert(data_path="rotation_quaternion",frame=frame)
        bone.keyframe_insert(data_path="scale",frame=frame)
    return {
        "frame":frame,
        "trace":trace,
        "wrist":wrist,
        "clearance":clearance,
    }


def lower_names(canonical: dict) -> list[str]:
    return [
        canonical["canonical_bones"][name]["rig_bone"]
        for name in (
            "pelvis",
            "left_thigh","left_shin","left_foot","left_toes",
            "right_thigh","right_shin","right_foot","right_toes",
        )
    ]


def render_previews(
    armature,
    canonical,
    contract,
    preview_dir: Path,
) -> tuple[list[str],dict]:
    preview_dir.mkdir(parents=True,exist_ok=True)
    scene=bpy.context.scene
    resolution=int(contract["preview"]["resolution"])
    engine=visual_gate.configure_workbench(scene,resolution)
    video_api=arm_a.configure_video_output(scene)
    scene.frame_start=int(contract["timeline"]["frame_start"])
    scene.frame_end=int(contract["timeline"]["frame_end"])
    scene.render.fps=int(contract["timeline"]["fps"])
    scene.render.ffmpeg.format=contract["preview"]["container"]
    scene.render.ffmpeg.codec=contract["preview"]["codec"]
    scene.render.ffmpeg.constant_rate_factor="MEDIUM"

    scene.frame_set(scene.frame_start)
    camera,center_world,height=visual_gate.create_camera(
        armature,canonical
    )
    files=[]
    for view_name in contract["preview"]["views"]:
        visual_gate.set_view(
            camera,center_world,armature,canonical,view_name,height
        )
        path=preview_dir/f"bras_bas_en_avant_second_{view_name.lower()}.mp4"
        if path.exists():
            path.unlink()
        scene.render.filepath=str(path)
        result=bpy.ops.render.render(animation=True)
        require("FINISHED" in result,f"{view_name}: render failed: {result}")
        require(path.exists(),f"{view_name}: preview missing: {path}")
        files.append(str(path))
    return files,{
        "engine":engine,
        "video_output_api":video_api,
        "views":list(contract["preview"]["views"]),
        "resolution":resolution,
    }


def validate_animation(
    armature,
    roles,
    lower_reference,
    boundary_pose,
    contract,
) -> dict:
    scene=bpy.context.scene
    frame_start=int(contract["timeline"]["frame_start"])
    frame_end=int(contract["timeline"]["frame_end"])
    boundary=int(contract["timeline"]["shared_boundary_frame"])
    lower_limit=float(
        contract["validation"]["lower_body_locked_local_matrix_error_max"]
    )
    boundary_limit=float(
        contract["validation"]["boundary_output_local_matrix_error_max"]
    )
    q_limit=float(
        contract["validation"]["minimum_consecutive_quaternion_dot"]
    )

    previous_q={}
    min_dot=1.0
    max_step=0.0
    max_lower_error=0.0
    boundary_steps={}
    frame_rows=[]

    for frame in range(frame_start,frame_end+1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        lower_error=max(
            (
                arm_a.matrix_max_error(
                    armature.pose.bones[name].matrix_basis,
                    lower_reference[name],
                )
                for name in lower_reference
            ),
            default=0.0,
        )
        max_lower_error=max(max_lower_error,lower_error)
        require(
            lower_error <= lower_limit,
            f"Frame {frame}: lower-body drift {lower_error} > {lower_limit}.",
        )

        frame_step=0.0
        for rig_name in roles:
            q=armature.pose.bones[rig_name].matrix_basis.to_quaternion()
            q.normalize()
            prior=previous_q.get(rig_name)
            if prior is not None:
                dot=float(prior.dot(q))
                if dot < 0.0:
                    q.negate()
                    dot=float(prior.dot(q))
                min_dot=min(min_dot,dot)
                require(
                    dot >= q_limit-1e-9,
                    f"Frame {frame}: quaternion flip on {rig_name}: {dot}.",
                )
                step=math.degrees(prior.rotation_difference(q).angle)
                frame_step=max(frame_step,step)
                max_step=max(max_step,step)
            previous_q[rig_name]=q.copy()

        if frame in (boundary-1,boundary,boundary+1):
            boundary_steps[str(frame)]=frame_step
        frame_rows.append({
            "frame":frame,
            "lower_body_local_matrix_error":lower_error,
            "maximum_upper_chain_step_deg":frame_step,
        })

    scene.frame_set(boundary)
    boundary_error=max_pose_error(
        {name:armature.pose.bones[name].matrix_basis.copy() for name in boundary_pose},
        boundary_pose,
        set(boundary_pose),
    )
    require(
        boundary_error <= boundary_limit,
        f"Composed boundary output differs from accepted en_avant: "
        f"{boundary_error} > {boundary_limit}.",
    )

    return {
        "sample_count":len(frame_rows),
        "sampled_every_frame":True,
        "maximum_lower_body_local_matrix_error":max_lower_error,
        "minimum_consecutive_quaternion_dot":min_dot,
        "maximum_consecutive_upper_chain_step_deg":max_step,
        "boundary_output_local_matrix_error":boundary_error,
        "boundary_step_diagnostics_deg":boundary_steps,
        "frames":frame_rows,
    }


def main() -> None:
    args=parse_args()
    repo=Path(args.repo).resolve()
    canonical=load_json(args.canonical_profile)
    constraints=load_json(args.constraint_profile)
    retarget=load_json(args.retarget_profile)
    axis_contract=load_json(args.retarget_axis_contract)
    grammar=load_json(args.grammar_profile)
    intents=load_json(args.intent_spec)
    static_contract=load_json(args.static_contract)
    visual_contract=load_json(args.visual_contract)
    source_a=load_json(args.source_contract_a)
    source_b=load_json(args.source_contract_b)
    contract=load_json(args.composition_contract)
    report_path=Path(args.report).resolve()
    preview_dir=Path(args.preview_dir).resolve()

    composition.validate_contract(contract)
    require(source_a["phase"]=="10.7.1","Source A phase mismatch.")
    require(source_b["phase"]=="10.7.2","Source B phase mismatch.")
    require(
        source_a["contract_id"]==contract["sequence"][0]["source_contract_id"],
        "Source A contract id mismatch.",
    )
    require(
        source_b["contract_id"]==contract["sequence"][1]["source_contract_id"],
        "Source B contract id mismatch.",
    )
    arm_a.motion.validate_contract(source_a)
    arm_b.motion.validate_contract(source_b)

    source_glb=repo/canonical["source"]["path"]
    require(source_glb.exists(),f"Source GLB missing: {source_glb}")
    require(
        static_core.sha256_file(source_glb)==canonical["source"]["sha256"],
        "Source GLB changed after accepted rig calibration.",
    )

    bpy.ops.wm.read_factory_settings(use_empty=True)
    imported=bpy.ops.import_scene.gltf(filepath=str(source_glb))
    require("FINISHED" in imported,f"glTF import failed: {imported}")
    armature=static_core.find_armature(canonical["source"]["armature"])
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
    runtime["grammar_profile"]=grammar
    runtime["intent_spec"]=intents
    runtime["pose_solver"]=pose_solver
    runtime["retarget_solver"]=retarget_solver

    roles,hierarchy=arm_a.actual_upper_chain(
        armature,canonical,static_contract
    )
    roles_b,hierarchy_b=arm_b.actual_upper_chain(
        armature,canonical,static_contract
    )
    require(roles==roles_b,"Accepted arm primitive role maps differ.")

    a_start,a_start_e=realize(
        arm_a,"bras_bas",armature,canonical,constraints,retarget,
        axis_contract,static_contract,visual_contract,runtime
    )
    a_end,a_end_e=realize(
        arm_a,"en_avant",armature,canonical,constraints,retarget,
        axis_contract,static_contract,visual_contract,runtime
    )
    b_start,b_start_e=realize(
        arm_b,"en_avant",armature,canonical,constraints,retarget,
        axis_contract,static_contract,visual_contract,runtime
    )
    b_end,b_end_e=realize(
        arm_b,"second",armature,canonical,constraints,retarget,
        axis_contract,static_contract,visual_contract,runtime
    )

    shared_error=max_pose_error(a_end,b_start)
    shared_limit=float(
        contract["validation"]["shared_boundary_local_matrix_error_max"]
    )
    require(
        shared_error <= shared_limit,
        f"Accepted en_avant boundary mismatch {shared_error} > {shared_limit}.",
    )

    seg_a=make_segment_contract(source_a,1)
    seg_b=make_segment_contract(source_b,61)
    moving=set(roles)

    a_locked=canonicalize_locked_endpoint(
        arm_a,a_start,a_end,moving,seg_a
    )
    b_locked=canonicalize_locked_endpoint(
        arm_b,b_start,b_end,moving,seg_b
    )

    cache_a=arm_a.prepare_motion_cache(
        armature,roles,a_start,a_end,seg_a
    )
    wrist_a=arm_a.prepare_wrist_2dof_cache(
        canonical,a_start_e,a_end_e,cache_a
    )
    cache_b=arm_b.prepare_motion_cache(
        armature,roles,b_start,b_end,seg_b
    )
    wrist_b=arm_b.prepare_wrist_2dof_cache(
        canonical,b_start_e,b_end_e,cache_b
    )

    for name,matrix in a_start.items():
        armature.pose.bones[name].matrix_basis=matrix.copy()
    bpy.context.view_layer.update()

    lower_ref={
        name:armature.pose.bones[name].matrix_basis.copy()
        for name in lower_names(canonical)
    }

    generation={"segment_a":[],"segment_b":[]}
    for frame in range(1,62):
        generation["segment_a"].append(
            apply_segment_frame(
                arm_a,armature,canonical,runtime,a_start,
                cache_a,wrist_a,seg_a,frame
            )
        )
    for frame in range(62,122):
        generation["segment_b"].append(
            apply_segment_frame(
                arm_b,armature,canonical,runtime,b_start,
                cache_b,wrist_b,seg_b,frame
            )
        )

    scene=bpy.context.scene
    scene.frame_start=1
    scene.frame_end=121
    scene.render.fps=30
    scene.frame_set(1)

    diagnostics=validate_animation(
        armature,roles,lower_ref,a_end,contract
    )
    previews,preview_evidence=render_previews(
        armature,canonical,contract,preview_dir
    )

    report={
        "phase":PHASE,
        "contract_id":contract["contract_id"],
        "source_contracts":[
            {"phase":source_a["phase"],"contract_id":source_a["contract_id"]},
            {"phase":source_b["phase"],"contract_id":source_b["contract_id"]},
        ],
        "shared_boundary":{
            "pose":"en_avant",
            "frame":61,
            "accepted_realization_local_matrix_error":shared_error,
            "limit":shared_limit,
            "single_key_authority":"10.7.1_END",
            "duplicate_boundary_key_inserted":False,
        },
        "role_hierarchy":{
            "segment_a":hierarchy,
            "segment_b":hierarchy_b,
        },
        "locked_endpoint_normalization":{
            "segment_a":a_locked,
            "segment_b":b_locked,
        },
        "generation":{
            "segment_a_frames":len(generation["segment_a"]),
            "segment_b_frames":len(generation["segment_b"]),
            "total_unique_frames":121,
            "source_primitive_math_reimplemented":False,
        },
        "diagnostics":diagnostics,
        "preview":{**preview_evidence,"files":previews},
        "automated_gate":{
            "source_10_7_1_reused":True,
            "source_10_7_2_reused":True,
            "shared_en_avant_matrix_identity":True,
            "single_boundary_key_authority":True,
            "no_inserted_hold_frames":True,
            "lower_body_locked":True,
            "quaternion_flip_free":True,
            "sampled_every_frame":True,
            "single_humanoid_motion_authority":True,
            "primitive_math_reimplementation_absent":True,
            "glb_exported":False,
        },
        "human_visual_gate":{
            "required":True,
            "status":"PENDING_REVIEW",
            "question":(
                "Does bras_bas -> en_avant -> second read as one clean "
                "two-primitive port-de-bras chain with no boundary snap, "
                "double-set, jitter, or artificial hold at en_avant?"
            ),
            "automated_aesthetic_verdict":False,
        },
    }
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")

    print("PHASE10_9_1_ARM_COMPOSITION_AUTOMATED_PROOF=PASS")
    print(f"REPORT={report_path}")
    print(f"PREVIEWS={';'.join(previews)}")
    print("HUMAN_VISUAL_REVIEW=PENDING")
    print("GLB_EXPORT=NOT_PERFORMED")


if __name__=="__main__":
    main()
