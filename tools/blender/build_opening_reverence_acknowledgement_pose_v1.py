"""Phase 10.11.1 static opening-reverence acknowledgement pose proof."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import bpy


PHASE="10.11.1"
HERE=Path(__file__).resolve().parent
REPO_DEFAULT=HERE.parents[1]
BALLET_TOOLS=REPO_DEFAULT/"tools"/"ballet_motion"
for path in (HERE,BALLET_TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402
import render_foundation_pose_visual_gate_v1 as visual_gate  # noqa: E402
import build_foundation_transition_v1 as arm_motion  # noqa: E402
import build_lower_body_fifth_to_plie_v1 as lower_motion  # noqa: E402
import opening_reverence_pose as reverence  # noqa: E402


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
    p.add_argument("--reverence-contract",required=True)
    p.add_argument("--lower-motion-contract",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--preview-dir",required=True)
    return p.parse_args(sys.argv[sys.argv.index("--")+1:])


def require(condition: bool,message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def snapshot(armature: bpy.types.Object) -> dict:
    return {
        bone.name:bone.matrix_basis.copy()
        for bone in armature.pose.bones
    }


def matrix_max_error(a,b) -> float:
    return max(
        abs(float(a[row][col])-float(b[row][col]))
        for row in range(4)
        for col in range(4)
    )


def apply_canonical_x_increment(
    armature: bpy.types.Object,
    canonical: dict,
    canonical_name: str,
    angle_deg: float,
) -> None:
    bone=canonical["canonical_bones"][canonical_name]
    rig_name=bone["rig_bone"]
    pose_bone=armature.pose.bones[rig_name]
    current_canonical=static_core.canonical_basis_from_rig_pose(
        pose_bone,
        bone,
    )
    desired_canonical=(
        current_canonical
        @ static_core.rotation_x(float(angle_deg))
    )
    desired_rig=static_core.rig_basis_from_canonical_pose(
        bone,
        desired_canonical,
    )
    static_core.apply_absolute_rig_rotation_via_matrix_basis(
        armature,
        rig_name,
        desired_rig,
    )


def contact_proof(
    armature,
    runtime,
    static_contract,
) -> dict:
    heights=static_core.contact_heights(
        armature,
        runtime["anchors"],
        runtime["up_axis"],
        float(runtime["sampling"]["low_height_quantile"]),
    )
    mode=static_contract["root_translation_modes"]["plie"]
    proof=static_core.contact_errors(
        mode,
        runtime["rest_heights"],
        heights,
    )
    require(
        proof["max_abs_error"] <= runtime["contact_tolerance"],
        "Reverence acknowledgement lost sampled demi-plié full-foot contact: "
        f"{proof['max_abs_error']} > {runtime['contact_tolerance']}.",
    )
    return {
        "mode":mode,
        "heights":heights,
        "proof":proof,
    }


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

    camera,center_world,height=visual_gate.create_camera(
        armature,
        canonical,
    )
    files=[]
    for view_name in contract["preview"]["views"]:
        visual_gate.set_view(
            camera,
            center_world,
            armature,
            canonical,
            view_name,
            height,
        )
        path=preview_dir/f"opening_reverence_acknowledgement_{view_name.lower()}.png"
        if path.exists():
            path.unlink()
        scene.render.filepath=str(path)
        scene.render.image_settings.file_format="PNG"
        result=bpy.ops.render.render(write_still=True)
        require("FINISHED" in result,f"{view_name}: render failed: {result}")
        require(path.exists(),f"{view_name}: preview missing: {path}")
        files.append(str(path))

    return files,{
        "engine":engine,
        "views":list(contract["preview"]["views"]),
        "resolution":resolution,
        "front_view_semantics":"AUDIENCE_VIEW_CANONICAL_BODY_FRONT",
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
    contract=load_json(args.reverence_contract)
    lower_contract=load_json(args.lower_motion_contract)

    report_path=Path(args.report).resolve()
    preview_dir=Path(args.preview_dir).resolve()

    reverence.validate_contract(contract)
    lower_motion.motion.validate_contract(lower_contract)
    require(
        lower_contract["contract_id"]
        == contract["source_pose_authority"]["lower_body_source_contract_id"],
        "Reverence lower-body source contract mismatch.",
    )
    require(canonical["phase"]=="10.6.2","Requires accepted 10.6.2.")
    require(retarget["phase"]=="10.6.6","Requires accepted 10.6.6.")
    require(static_contract["phase"]=="10.6.7","Requires accepted 10.6.7.")
    require(visual_contract["phase"]=="10.6.8","Requires accepted 10.6.8.")
    require(
        retarget["gate"]["orientation_retarget_pass"],
        "Accepted retarget gate is not PASS.",
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

    # Old reverence attempt lesson: imported GLB action must never be allowed
    # to overwrite authored proof poses during background evaluation.
    if armature.animation_data is not None:
        armature.animation_data_clear()
    for obj in bpy.context.scene.objects:
        if obj.animation_data is not None:
            obj.animation_data_clear()

    runtime=visual_gate.prepare_contact_runtime(
        armature,
        canonical,
        static_contract,
    )
    pose_solver,retarget_solver=(
        static_core.load_ballet_motion_runtime_modules(repo)
    )
    runtime["grammar_profile"]=grammar
    runtime["intent_spec"]=intents
    runtime["pose_solver"]=pose_solver
    runtime["retarget_solver"]=retarget_solver

    # Realize and capture the exact accepted bras-bas arm source first.
    visual_gate.realize_pose(
        contract["source_pose_authority"]["arm_pose"],
        armature,
        canonical,
        constraints,
        retarget,
        axis_contract,
        static_contract,
        runtime,
    )
    bras_bas_pose=snapshot(armature)

    arm_roles,_=arm_motion.actual_upper_chain(
        armature,
        canonical,
        static_contract,
    )
    arm_names=set(arm_roles)

    # Sample the already accepted fifth -> plié motion at its midpoint rather
    # than inventing a new leg pose. This gives a restrained demi-plié with
    # the same full-foot contact authority used in Phase 10.8.1.
    fifth_pose,_=lower_motion.realize_endpoint(
        "fifth",
        armature,
        canonical,
        constraints,
        retarget,
        axis_contract,
        static_contract,
        runtime,
    )
    plie_endpoint,_=lower_motion.realize_endpoint(
        "plie",
        armature,
        canonical,
        constraints,
        retarget,
        axis_contract,
        static_contract,
        runtime,
    )
    moving,_,partition=lower_motion.endpoint_partition(
        armature,
        fifth_pose,
        plie_endpoint,
        canonical,
        lower_contract,
    )
    root_name=canonical["canonical_bones"]["pelvis"]["rig_bone"]
    motion_cache=lower_motion.prepare_motion_cache(
        fifth_pose,
        plie_endpoint,
        moving,
        root_name,
        lower_contract,
    )
    sample_frame=int(
        contract["source_pose_authority"]["lower_body_sample_frame"]
    )
    lower_sample_evidence=lower_motion.set_frame_pose(
        armature,
        fifth_pose,
        plie_endpoint,
        moving,
        motion_cache,
        canonical,
        runtime,
        static_contract,
        sample_frame,
        lower_contract,
    )
    demi_plie_pose=snapshot(armature)

    # Overlay only explicit accepted bras-bas arm-chain local matrices.
    for name in arm_names:
        armature.pose.bones[name].matrix_basis=bras_bas_pose[name].copy()
    bpy.context.view_layer.update()

    arm_overlay_pose=snapshot(armature)

    # Add only the explicitly contracted axial acknowledgement overlay.
    overlay=contract["acknowledgement_overlay"]
    trunk_total=float(overlay["trunk_extra_flexion_deg"])
    for route in overlay["trunk_routes"]:
        apply_canonical_x_increment(
            armature,
            canonical,
            route["bone"],
            trunk_total*float(route["weight"]),
        )
    apply_canonical_x_increment(
        armature,
        canonical,
        "neck",
        float(overlay["neck_flexion_deg"]),
    )
    apply_canonical_x_increment(
        armature,
        canonical,
        "head",
        float(overlay["head_flexion_deg"]),
    )
    bpy.context.view_layer.update()

    final_pose=snapshot(armature)

    lower_names={
        canonical["canonical_bones"][name]["rig_bone"]
        for name in (
            "pelvis",
            "left_thigh","left_shin","left_foot","left_toes",
            "right_thigh","right_shin","right_foot","right_toes",
        )
    }
    lower_error=max(
        matrix_max_error(final_pose[name],demi_plie_pose[name])
        for name in lower_names
    )
    require(
        lower_error
        <= float(
            contract["validation"][
                "lower_contact_chain_local_matrix_error_max"
            ]
        ),
        f"Accepted sampled demi-plié lower chain changed: {lower_error}.",
    )

    arm_error=max(
        matrix_max_error(final_pose[name],bras_bas_pose[name])
        for name in arm_names
    )
    require(
        arm_error
        <= float(
            contract["validation"][
                "arm_explicit_chain_local_matrix_error_max"
            ]
        ),
        f"Accepted bras-bas arm local matrices changed: {arm_error}.",
    )

    allowed_canonical=set(
        contract["validation"]["allowed_new_orientation_bones"]
    )
    allowed_rig={
        canonical["canonical_bones"][name]["rig_bone"]
        for name in allowed_canonical
    }
    changed_after_overlay={
        name
        for name in final_pose
        if matrix_max_error(final_pose[name],arm_overlay_pose[name]) > 1e-7
    }
    unexpected=sorted(changed_after_overlay-allowed_rig)
    require(
        not unexpected,
        "Reverence overlay changed bones outside axial acknowledgement set: "
        + ", ".join(unexpected),
    )

    contact=contact_proof(
        armature,
        runtime,
        static_contract,
    )

    hand_offsets={}
    inner_q=float(runtime["hand_sampling"]["inner_edge_quantile"])
    minimum=float(contract["validation"]["minimum_hand_side_offset"])
    for side in ("left","right"):
        measurement=static_core.hand_mesh_inner_edge(
            armature,
            canonical,
            runtime["hand_samples"][side],
            side,
            inner_q,
        )
        offset=float(measurement["side_offset"])
        hand_offsets[side]=offset
        require(
            offset >= minimum-1e-9,
            f"{side} hand crosses centerline in reverence pose: {offset}.",
        )

    previews,preview_evidence=render_previews(
        armature,
        canonical,
        contract,
        preview_dir,
    )

    report={
        "phase":PHASE,
        "contract_id":contract["contract_id"],
        "source_authority":{
            "lower_motion_phase":"10.8.1",
            "lower_motion_contract_id":lower_contract["contract_id"],
            "lower_sample_frame":sample_frame,
            "lower_sample_progress":float(lower_sample_evidence["progress"]),
            "arm_pose":"bras_bas",
            "imported_action_cleared":True,
        },
        "acknowledgement_overlay":overlay,
        "lower_motion_partition":partition,
        "diagnostics":{
            "lower_contact_chain_local_matrix_error":lower_error,
            "arm_explicit_chain_local_matrix_error":arm_error,
            "new_orientation_changed_rig_bones":sorted(changed_after_overlay),
            "unexpected_changed_rig_bones":unexpected,
            "full_foot_contact_max_abs_error":float(
                contact["proof"]["max_abs_error"]
            ),
            "contact_tolerance":float(runtime["contact_tolerance"]),
            "hand_side_offsets":hand_offsets,
        },
        "preview":{**preview_evidence,"files":previews},
        "automated_gate":{
            "accepted_fifth_to_plie_motion_reused":True,
            "accepted_bras_bas_reused":True,
            "independent_arm_authoring_absent":True,
            "independent_leg_authoring_absent":True,
            "axial_overlay_only":True,
            "lower_chain_exact":True,
            "arm_chain_exact":True,
            "full_foot_contact_pass":True,
            "hand_centerline_pass":True,
            "imported_action_cleared":True,
            "animation_authored":False,
            "glb_exported":False,
        },
        "human_visual_gate":{
            "required":True,
            "status":"PENDING_REVIEW",
            "questions":contract["human_visual_questions"],
            "automated_aesthetic_verdict":False,
        },
    }

    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(
        json.dumps(report,indent=2),
        encoding="utf-8",
    )

    print("PHASE10_11_1_REVERENCE_ACKNOWLEDGEMENT_POSE_AUTOMATED_PROOF=PASS")
    print(f"PREVIEWS={';'.join(previews)}")
    print(f"CONTACT_MAX={contact['proof']['max_abs_error']}")
    print(f"HAND_OFFSETS={hand_offsets['left']} / {hand_offsets['right']}")
    print("HUMAN_VISUAL_REVIEW=PENDING")
    print("ANIMATION_AUTHORED=NO")
    print("GLB_EXPORT=NOT_PERFORMED")
    print(f"REPORT={report_path}")


if __name__=="__main__":
    main()
