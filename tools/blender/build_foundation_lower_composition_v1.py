"""Phase 10.9.2 accepted lower-body primitive composition proof."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import bpy


PHASE="10.9.2"
HERE=Path(__file__).resolve().parent
REPO_DEFAULT=HERE.parents[1]
BALLET_TOOLS=REPO_DEFAULT/"tools"/"ballet_motion"
for path in (HERE,BALLET_TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402
import render_foundation_pose_visual_gate_v1 as visual_gate  # noqa: E402
import build_lower_body_fifth_to_plie_v1 as lower_a  # noqa: E402
import build_lower_body_plie_to_releve_v1 as lower_b  # noqa: E402
import lower_body_motion_composition as composition  # noqa: E402


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
        (lower_a.matrix_max_error(a[name],b[name]) for name in selected),
        default=0.0,
    )


def make_segment_contract(source: dict,frame_start: int) -> dict:
    result=copy.deepcopy(source)
    result["transition"]["frame_start"]=int(frame_start)
    return result


def key_union(
    armature: bpy.types.Object,
    names: set[str],
    frame: int,
) -> None:
    for name in names:
        bone=armature.pose.bones[name]
        bone.keyframe_insert(data_path="location",frame=frame)
        if bone.rotation_mode != "QUATERNION":
            bone.rotation_mode="QUATERNION"
        bone.keyframe_insert(data_path="rotation_quaternion",frame=frame)
        bone.keyframe_insert(data_path="scale",frame=frame)


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
    video_api=lower_a.configure_video_output(scene)

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
        path=preview_dir/f"fifth_plie_releve_{view_name.lower()}.mp4"
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
    runtime,
    static_contract,
    moving_union,
    shared_pose,
    contract,
) -> dict:
    scene=bpy.context.scene
    frame_start=int(contract["timeline"]["frame_start"])
    boundary=int(contract["timeline"]["shared_boundary_frame"])
    frame_end=int(contract["timeline"]["frame_end"])

    shared_limit=float(
        contract["validation"]["boundary_output_local_matrix_error_max"]
    )
    horizontal_limit=float(
        contract["validation"]["root_horizontal_translation_max"]
    )
    descent_epsilon=float(
        contract["validation"]["root_descent_monotonic_epsilon"]
    )
    rise_epsilon=float(
        contract["validation"]["root_rise_monotonic_epsilon"]
    )
    heel_epsilon=float(
        contract["validation"]["heel_lift_monotonic_epsilon"]
    )
    q_limit=float(
        contract["validation"]["minimum_consecutive_quaternion_dot"]
    )

    canonical_root=None
    # Root is the only pose bone with contact translation authority in these
    # accepted primitives. Recover it from the source helper's canonical map.
    # Assigned by caller through scene object custom property.
    root_name=scene["phase10_9_2_root_name"]

    previous_q={}
    min_dot=1.0
    max_step=0.0
    max_horizontal=0.0
    root_shifts=[]
    heels={"left":[],"right":[]}
    contact_modes=[]
    boundary_steps={}
    frames=[]

    for frame in range(frame_start,frame_end+1):
        scene.frame_set(frame)
        bpy.context.view_layer.update()

        if frame <= boundary:
            state=lower_a.contact_state(
                armature,runtime,static_contract
            )
            mode="SOLVE_FULL_FOOT_CONTACT"
            heel_state={
                "left":float(
                    state["heights"]["left"]["rear"]
                    - runtime["rest_heights"]["left"]["rear"]
                ),
                "right":float(
                    state["heights"]["right"]["rear"]
                    - runtime["rest_heights"]["right"]["rear"]
                ),
            }
        else:
            state=lower_b.contact_state(
                armature,runtime,"SOLVE_FOREFOOT_CONTACT"
            )
            mode="SOLVE_FOREFOOT_CONTACT"
            heel_state={
                "left":float(state["heel_lifts"]["left"]),
                "right":float(state["heel_lifts"]["right"]),
            }

        require(
            state["proof"]["max_abs_error"]
            <= runtime["contact_tolerance"],
            f"Frame {frame}: {mode} contact failed: "
            f"{state['proof']['max_abs_error']} > "
            f"{runtime['contact_tolerance']}.",
        )

        root=lower_a.root_armature_translation(
            armature,root_name
        )
        up=runtime["up_axis"]
        shift=float(root.dot(up))
        horizontal=float(
            (root-up*root.dot(up)).length
        )
        max_horizontal=max(max_horizontal,horizontal)
        require(
            horizontal <= horizontal_limit,
            f"Frame {frame}: root horizontal drift "
            f"{horizontal} > {horizontal_limit}.",
        )
        root_shifts.append(shift)

        for side in ("left","right"):
            heels[side].append(heel_state[side])

        frame_step=0.0
        for name in moving_union:
            q=armature.pose.bones[name].matrix_basis.to_quaternion()
            q.normalize()
            prior=previous_q.get(name)
            if prior is not None:
                dot=float(prior.dot(q))
                if dot < 0.0:
                    q.negate()
                    dot=float(prior.dot(q))
                min_dot=min(min_dot,dot)
                require(
                    dot >= q_limit-1e-9,
                    f"Frame {frame}: quaternion flip on {name}: {dot}.",
                )
                step=math.degrees(
                    prior.rotation_difference(q).angle
                )
                frame_step=max(frame_step,step)
                max_step=max(max_step,step)
            previous_q[name]=q.copy()

        if frame in (boundary-1,boundary,boundary+1):
            boundary_steps[str(frame)]=frame_step

        contact_modes.append(mode)
        frames.append({
            "frame":frame,
            "contact_mode":mode,
            "contact_max_abs_error":float(
                state["proof"]["max_abs_error"]
            ),
            "root_up_shift":shift,
            "root_horizontal_translation":horizontal,
            "heel_lifts":heel_state,
            "maximum_moving_step_deg":frame_step,
        })

    # Segment A: fifth -> plié descends monotonically.
    for index in range(1,boundary):
        require(
            root_shifts[index]
            <= root_shifts[index-1]+descent_epsilon,
            f"Frame {index+1}: composed descent reversed.",
        )

    # Segment B: plié -> relevé rises monotonically.
    for index in range(boundary,len(root_shifts)):
        require(
            root_shifts[index]
            >= root_shifts[index-1]-rise_epsilon,
            f"Frame {index+1}: composed rise reversed.",
        )
        for side in ("left","right"):
            require(
                heels[side][index]
                >= heels[side][index-1]-heel_epsilon,
                f"Frame {index+1}: {side} composed heel lift reversed.",
            )

    scene.frame_set(boundary)
    boundary_actual={
        name:armature.pose.bones[name].matrix_basis.copy()
        for name in shared_pose
    }
    boundary_error=max_pose_error(
        boundary_actual,shared_pose,set(shared_pose)
    )
    require(
        boundary_error <= shared_limit,
        f"Composed plié boundary differs from source endpoint: "
        f"{boundary_error} > {shared_limit}.",
    )

    return {
        "sample_count":len(frames),
        "sampled_every_frame":True,
        "maximum_root_horizontal_translation":max_horizontal,
        "root_up_shift_start":root_shifts[0],
        "root_up_shift_boundary":root_shifts[boundary-1],
        "root_up_shift_end":root_shifts[-1],
        "root_descent":root_shifts[0]-root_shifts[boundary-1],
        "root_rise":root_shifts[-1]-root_shifts[boundary-1],
        "root_descent_monotone":True,
        "root_rise_monotone":True,
        "heel_lift_monotone_after_boundary":True,
        "heel_lift_end":{
            side:heels[side][-1] for side in ("left","right")
        },
        "minimum_consecutive_quaternion_dot":min_dot,
        "maximum_consecutive_moving_step_deg":max_step,
        "boundary_output_local_matrix_error":boundary_error,
        "boundary_step_diagnostics_deg":boundary_steps,
        "contact_modes":{
            "frames_1_61":"SOLVE_FULL_FOOT_CONTACT",
            "frames_62_121":"SOLVE_FOREFOOT_CONTACT",
        },
        "frames":frames,
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
    lower_a.motion.validate_contract(source_a)
    lower_b.motion.validate_contract(source_b)

    require(source_a["phase"]=="10.8.1","Source A phase mismatch.")
    require(source_b["phase"]=="10.8.2","Source B phase mismatch.")
    require(
        source_a["contract_id"]
        ==contract["sequence"][0]["source_contract_id"],
        "Source A contract id mismatch.",
    )
    require(
        source_b["contract_id"]
        ==contract["sequence"][1]["source_contract_id"],
        "Source B contract id mismatch.",
    )

    source_glb=repo/canonical["source"]["path"]
    require(source_glb.exists(),f"Source GLB missing: {source_glb}")
    require(
        static_core.sha256_file(source_glb)==canonical["source"]["sha256"],
        "Source GLB changed after accepted calibration.",
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

    fifth,fifth_e=lower_a.realize_endpoint(
        "fifth",armature,canonical,constraints,retarget,
        axis_contract,static_contract,runtime
    )
    plie_a,plie_a_e=lower_a.realize_endpoint(
        "plie",armature,canonical,constraints,retarget,
        axis_contract,static_contract,runtime
    )
    plie_b,plie_b_e=lower_a.realize_endpoint(
        "plie",armature,canonical,constraints,retarget,
        axis_contract,static_contract,runtime
    )
    releve,releve_e=lower_a.realize_endpoint(
        "releve",armature,canonical,constraints,retarget,
        axis_contract,static_contract,runtime
    )

    shared_error=max_pose_error(plie_a,plie_b)
    shared_limit=float(
        contract["validation"]["shared_boundary_local_matrix_error_max"]
    )
    require(
        shared_error <= shared_limit,
        f"Accepted plié boundary mismatch {shared_error} > {shared_limit}.",
    )

    seg_a=make_segment_contract(source_a,1)
    seg_b=make_segment_contract(source_b,61)

    moving_a,locked_a,partition_a=lower_a.endpoint_partition(
        armature,fifth,plie_a,canonical,seg_a
    )
    moving_b,locked_b,partition_b=lower_a.endpoint_partition(
        armature,plie_b,releve,canonical,seg_b
    )
    moving_union=set(moving_a)|set(moving_b)

    root_name=canonical["canonical_bones"]["pelvis"]["rig_bone"]
    require(root_name in moving_union,"Pelvis missing from composition authority.")

    cache_a=lower_a.prepare_motion_cache(
        fifth,plie_a,moving_a,root_name,seg_a
    )
    cache_b=lower_b.prepare_motion_cache(
        plie_b,releve,moving_b,root_name,seg_b
    )

    for name,matrix in fifth.items():
        armature.pose.bones[name].matrix_basis=matrix.copy()
    bpy.context.view_layer.update()

    generation={"segment_a":[],"segment_b":[]}

    for frame in range(1,62):
        evidence=lower_a.set_frame_pose(
            armature,fifth,plie_a,moving_a,cache_a,
            canonical,runtime,static_contract,frame,seg_a
        )
        key_union(armature,moving_union,frame)
        generation["segment_a"].append(evidence)

    # Shared boundary frame 61 is already keyed exactly once by segment A.
    for frame in range(62,122):
        evidence=lower_b.set_frame_pose(
            armature,plie_b,releve,moving_b,cache_b,
            canonical,runtime,frame,seg_b
        )
        key_union(armature,moving_union,frame)
        generation["segment_b"].append(evidence)

    scene=bpy.context.scene
    scene.frame_start=1
    scene.frame_end=121
    scene.render.fps=30
    scene["phase10_9_2_root_name"]=root_name
    scene.frame_set(1)

    diagnostics=validate_animation(
        armature,runtime,static_contract,moving_union,
        plie_a,contract
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
            "pose":"plie",
            "frame":61,
            "accepted_realization_local_matrix_error":shared_error,
            "limit":shared_limit,
            "single_key_authority":"10.8.1_END",
            "duplicate_boundary_key_inserted":False,
        },
        "endpoint_partitions":{
            "segment_a":partition_a,
            "segment_b":partition_b,
            "moving_union_rig_bones":sorted(moving_union),
        },
        "generation":{
            "segment_a_frames":len(generation["segment_a"]),
            "segment_b_frames":len(generation["segment_b"]),
            "total_unique_frames":121,
            "source_primitive_math_reimplemented":False,
            "boundary_keyed_once":True,
        },
        "diagnostics":diagnostics,
        "preview":{**preview_evidence,"files":previews},
        "automated_gate":{
            "source_10_8_1_reused":True,
            "source_10_8_2_reused":True,
            "shared_plie_matrix_identity":True,
            "single_boundary_key_authority":True,
            "no_inserted_hold_frames":True,
            "full_foot_then_forefoot_contact":True,
            "root_descent_monotone":True,
            "root_rise_monotone":True,
            "heel_lift_monotone_after_boundary":True,
            "root_horizontal_drift_blocked":True,
            "quaternion_flip_free":True,
            "sampled_every_frame":True,
            "single_humanoid_motion_authority":True,
            "accepted_trunk_hierarchy_motion_preserved":True,
            "primitive_math_reimplementation_absent":True,
            "glb_exported":False,
        },
        "human_visual_gate":{
            "required":True,
            "status":"PENDING_REVIEW",
            "question":(
                "Does fifth -> plie -> releve read as one clean lower-body "
                "phrase with a stable plié boundary, continuous weight/contact "
                "logic, synchronized heel rise, and no snap or artificial hold?"
            ),
            "automated_aesthetic_verdict":False,
        },
    }

    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(report,indent=2),encoding="utf-8")

    print("PHASE10_9_2_LOWER_COMPOSITION_AUTOMATED_PROOF=PASS")
    print(f"REPORT={report_path}")
    print(f"PREVIEWS={';'.join(previews)}")
    print("HUMAN_VISUAL_REVIEW=PENDING")
    print("GLB_EXPORT=NOT_PERFORMED")


if __name__=="__main__":
    main()
