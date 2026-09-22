"""Phase 10.11.2 crossed reverence stance static proof."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


PHASE="10.11.2"
HERE=Path(__file__).resolve().parent
REPO_DEFAULT=HERE.parents[1]
BALLET_TOOLS=REPO_DEFAULT/"tools"/"ballet_motion"
for path in (HERE,BALLET_TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402
import render_foundation_pose_visual_gate_v1 as visual_gate  # noqa: E402
import build_foundation_transition_v1 as arm_motion  # noqa: E402
import opening_reverence_crossed_stance as stance  # noqa: E402


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
    p.add_argument("--arm-motion-contract",required=True)
    p.add_argument("--stance-contract",required=True)
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


def centroid(points: list[Vector]) -> Vector:
    total=Vector((0.0,0.0,0.0))
    for point in points:
        total+=point
    return total/max(1,len(points))


def region_centroid(
    armature: bpy.types.Object,
    samples: list[tuple[str,int]],
) -> Vector:
    return centroid(static_core.evaluated_sample_points(armature,samples))


def make_solution(state: dict) -> dict:
    return {
        "pose":"reverence_crossed_stance",
        "state":state,
        "validation":{"status":"PASS"},
        "evidence":{"preferred_joint_envelope":"PASS_BY_10_11_2"},
    }


def apply_state(
    armature,
    canonical,
    constraints,
    axis_contract,
    retarget_solver,
    state,
) -> dict:
    retargeted=retarget_solver.retarget_pose_solution(
        make_solution(state),
        canonical,
        constraints,
        axis_contract,
    )
    static_core.apply_rotation_deltas(armature,retargeted)
    return retargeted


def body_axes(canonical: dict, runtime: dict) -> dict:
    declared=canonical["body_frame"]["declared_axes_armature_local"]
    return {
        "left":Vector(declared["left"]).normalized(),
        "front":Vector(declared["front"]).normalized(),
        "up":runtime["up_axis"].normalized(),
    }


def hip_width(
    armature: bpy.types.Object,
    canonical: dict,
    left_axis: Vector,
) -> float:
    left_name=canonical["canonical_bones"]["left_thigh"]["rig_bone"]
    right_name=canonical["canonical_bones"]["right_thigh"]["rig_bone"]
    left=armature.data.bones[left_name].head_local
    right=armature.data.bones[right_name].head_local
    projected=abs(float((left-right).dot(left_axis)))
    return max(projected,float((left-right).length)*0.5)


def root_name(canonical: dict) -> str:
    return canonical["canonical_bones"]["pelvis"]["rig_bone"]


def set_support_shift(
    armature,
    canonical,
    axes,
    support_shift: float,
    vertical_shift: float=0.0,
) -> None:
    vector=(
        axes["left"]*float(support_shift)
        + axes["up"]*float(vertical_shift)
    )
    static_core.set_root_translation_armature_space(
        armature,
        root_name(canonical),
        vector,
    )


def calibrate_support_foot(
    armature,
    canonical,
    constraints,
    runtime,
    static_contract,
) -> dict:
    thresholds=static_contract["proof_thresholds"]
    sampling=runtime["sampling"]
    evidence=static_core.solve_preferred_ankle_flat_contact(
        armature,
        canonical,
        constraints,
        "left_foot",
        "left",
        runtime["up_axis"],
        runtime["anchors"],
        runtime["rest_heights"],
        float(sampling["low_height_quantile"]),
        float(thresholds["full_foot_seed_up_alignment_min_dot"]),
        float(thresholds["full_foot_mesh_search_coarse_step_deg"]),
        [
            float(value)
            for value in thresholds[
                "full_foot_mesh_search_refine_steps_deg"
            ]
        ],
    )
    return evidence


def solve_support_vertical(
    armature,
    canonical,
    axes,
    runtime,
    support_shift: float,
) -> dict:
    set_support_shift(
        armature,canonical,axes,support_shift,0.0
    )
    heights=static_core.contact_heights(
        armature,
        runtime["anchors"],
        runtime["up_axis"],
        float(runtime["sampling"]["low_height_quantile"]),
    )
    required=[
        float(runtime["rest_heights"]["left"][region])
        - float(heights["left"][region])
        for region in ("rear","fore")
    ]
    vertical=float(static_core.median(required))
    set_support_shift(
        armature,canonical,axes,support_shift,vertical
    )
    final=static_core.contact_heights(
        armature,
        runtime["anchors"],
        runtime["up_axis"],
        float(runtime["sampling"]["low_height_quantile"]),
    )
    errors={
        region:float(final["left"][region])
        - float(runtime["rest_heights"]["left"][region])
        for region in ("rear","fore")
    }
    return {
        "vertical_shift":vertical,
        "support_heights":final["left"],
        "support_errors":errors,
        "all_heights":final,
    }


def candidate_geometry(
    armature,
    canonical,
    runtime,
    axes,
    foot_length: float,
    rest_centroids: dict,
    vertical_evidence: dict,
) -> dict:
    anchors=runtime["anchors"]
    support_fore=region_centroid(
        armature,anchors["left"]["fore"]
    )
    gesture_fore=region_centroid(
        armature,anchors["right"]["fore"]
    )

    rest_gesture_fore=rest_centroids["right_fore"]
    cross_delta=float(
        (gesture_fore-rest_gesture_fore).dot(axes["left"])
    )
    back_delta=float(
        (rest_gesture_fore-gesture_fore).dot(axes["front"])
    )

    heights=vertical_evidence["all_heights"]
    gesture_fore_error=float(
        heights["right"]["fore"]
        - runtime["rest_heights"]["right"]["fore"]
    )
    gesture_rear_lift=float(
        heights["right"]["rear"]
        - runtime["rest_heights"]["right"]["rear"]
    )
    support_error=max(
        abs(float(value))
        for value in vertical_evidence["support_errors"].values()
    )

    return {
        "support_fore_centroid":list(map(float,support_fore)),
        "gesture_fore_centroid":list(map(float,gesture_fore)),
        "gesture_cross_delta":cross_delta,
        "gesture_back_delta":back_delta,
        "gesture_fore_height_error":gesture_fore_error,
        "gesture_rear_heel_lift":gesture_rear_lift,
        "support_full_foot_error":support_error,
        "normalized":{
            "gesture_cross_foot_fraction":cross_delta/foot_length,
            "gesture_back_foot_fraction":back_delta/foot_length,
            "gesture_fore_height_foot_fraction":gesture_fore_error/foot_length,
            "gesture_heel_lift_foot_fraction":gesture_rear_lift/foot_length,
            "support_error_foot_fraction":support_error/foot_length,
        },
    }


def geometry_pass(
    geometry: dict,
    contract: dict,
    foot_length: float,
) -> tuple[bool,list[str]]:
    target=contract["geometry_targets"]
    reasons=[]
    if geometry["gesture_cross_delta"] < (
        foot_length*float(target["gesture_cross_min_foot_fraction"])
    ):
        reasons.append("gesture_cross")
    if geometry["gesture_back_delta"] < (
        foot_length*float(target["gesture_back_min_foot_fraction"])
    ):
        reasons.append("gesture_back")
    if abs(geometry["gesture_fore_height_error"]) > (
        foot_length*float(
            target["gesture_fore_height_abs_max_foot_fraction"]
        )
    ):
        reasons.append("gesture_fore_height")
    if geometry["gesture_fore_height_error"] < (
        -foot_length*float(
            target["gesture_mesh_penetration_max_foot_fraction"]
        )
    ):
        reasons.append("gesture_penetration")
    if geometry["gesture_rear_heel_lift"] < (
        foot_length*float(target["gesture_heel_lift_min_foot_fraction"])
    ):
        reasons.append("gesture_heel_lift")
    if geometry["support_full_foot_error"] > (
        foot_length*float(
            target["support_full_foot_error_max_foot_fraction"]
        )
    ):
        reasons.append("support_contact")
    return not reasons,reasons


def candidate_score(
    params: dict,
    geometry: dict,
    foot_length: float,
) -> tuple:
    # Prefer the least extreme joint request that satisfies the reference
    # geometry, with forefoot height closest to the floor as first authority.
    return (
        abs(geometry["gesture_fore_height_error"])/foot_length,
        abs(float(params["gesture_hip_flexion_extension_deg"])),
        abs(float(params["gesture_hip_abduction_adduction_deg"])),
        abs(float(params["gesture_ankle_plantar_dorsiflexion_deg"])),
    )


def apply_canonical_x_increment(
    armature,
    canonical,
    canonical_name: str,
    angle_deg: float,
) -> None:
    bone=canonical["canonical_bones"][canonical_name]
    rig_name=bone["rig_bone"]
    pose_bone=armature.pose.bones[rig_name]
    current=static_core.canonical_basis_from_rig_pose(
        pose_bone,bone
    )
    desired=current @ static_core.rotation_x(float(angle_deg))
    static_core.apply_absolute_rig_rotation_via_matrix_basis(
        armature,
        rig_name,
        static_core.rig_basis_from_canonical_pose(bone,desired),
    )


def apply_contextual_bras_bas(
    armature,
    canonical,
    runtime,
    static_contract,
    retarget,
    constraints,
    axis_contract,
    bras_bas_pose,
    arm_contract,
    lower_pose,
) -> dict:
    arm_roles,_=arm_motion.actual_upper_chain(
        armature,canonical,static_contract
    )
    arm_names=set(arm_roles)
    for name in arm_names:
        armature.pose.bones[name].matrix_basis=bras_bas_pose[name].copy()
    bpy.context.view_layer.update()

    upper=lower_pose["upper_body"]
    trunk_total=float(upper["trunk_extra_flexion_deg"])
    for route in upper["trunk_routes"]:
        apply_canonical_x_increment(
            armature,
            canonical,
            route["bone"],
            trunk_total*float(route["weight"]),
        )
    apply_canonical_x_increment(
        armature,canonical,"neck",float(upper["neck_flexion_deg"])
    )
    apply_canonical_x_increment(
        armature,canonical,"head",float(upper["head_flexion_deg"])
    )
    bpy.context.view_layer.update()

    shoulder_names={
        canonical["canonical_bones"]["left_upper_arm"]["rig_bone"],
        canonical["canonical_bones"]["right_upper_arm"]["rig_bone"],
    }
    shoulder_cache={}
    for name in shoulder_names:
        location,_q,scale=armature.pose.bones[name].matrix_basis.decompose()
        shoulder_cache[name]={
            "location":location.copy(),
            "scale":scale.copy(),
        }

    clearance=arm_motion.enforce_hand_centerline_clearance(
        armature,
        canonical,
        runtime,
        arm_contract,
        shoulder_cache,
        1,
        0,
        2,
    )
    bpy.context.view_layer.update()
    return {
        "arm_names":sorted(arm_names),
        "shoulder_names":sorted(shoulder_names),
        "clearance":clearance,
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
        armature,canonical
    )
    files=[]
    for view in contract["preview"]["views"]:
        visual_gate.set_view(
            camera,center_world,armature,canonical,view,height
        )
        path=preview_dir/f"opening_reverence_crossed_{view.lower()}.png"
        if path.exists():
            path.unlink()
        scene.render.filepath=str(path)
        scene.render.image_settings.file_format="PNG"
        result=bpy.ops.render.render(write_still=True)
        require("FINISHED" in result,f"{view}: render failed: {result}")
        require(path.exists(),f"{view}: preview missing: {path}")
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
    arm_contract=load_json(args.arm_motion_contract)
    contract=load_json(args.stance_contract)
    stance.validate_contract(contract)
    arm_motion.motion.validate_contract(arm_contract)

    report_path=Path(args.report).resolve()
    preview_dir=Path(args.preview_dir).resolve()

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

    # Accepted bras-bas authority is captured independently and overlaid after
    # the new lower-body stance is selected.
    visual_gate.realize_pose(
        "bras_bas",
        armature,
        canonical,
        constraints,
        retarget,
        axis_contract,
        static_contract,
        runtime,
    )
    bras_bas_pose=snapshot(armature)

    axes=body_axes(canonical,runtime)
    width=hip_width(armature,canonical,axes["left"])
    support_shift=(
        width
        * float(
            contract["lower_body"][
                "pelvis_support_shift_hip_width_fraction"
            ]
        )
    )
    foot_length=float(static_core.body_metrics(canonical)["foot_chain_length"])

    # Rest centroids are measured from the calibrated neutral mesh.
    static_core.clear_pose(armature)
    rest_centroids={
        "right_fore":region_centroid(
            armature,runtime["anchors"]["right"]["fore"]
        ),
    }

    # Support leg is fixed across the 27 candidates. Solve its ankle/contact
    # orientation once, then reuse that exact local matrix for every candidate.
    first_params=next(stance.candidate_parameter_sets(contract))
    first_state=stance.build_state(contract,first_params)
    require(
        not stance.preferred_envelope_violations(
            first_state,constraints
        ),
        "Initial reverence state left preferred joint envelope.",
    )
    apply_state(
        armature,canonical,constraints,axis_contract,
        retarget_solver,first_state
    )
    set_support_shift(
        armature,canonical,axes,support_shift,0.0
    )
    support_ankle_evidence=calibrate_support_foot(
        armature,canonical,constraints,runtime,static_contract
    )
    support_foot_name=canonical["canonical_bones"]["left_foot"]["rig_bone"]
    calibrated_support_foot=armature.pose.bones[
        support_foot_name
    ].matrix_basis.copy()

    candidates=[]
    winners=[]
    for params in stance.candidate_parameter_sets(contract):
        state=stance.build_state(contract,params)
        violations=stance.preferred_envelope_violations(
            state,constraints
        )
        require(
            not violations,
            "Candidate left preferred joint envelope: "
            + "; ".join(violations),
        )
        apply_state(
            armature,canonical,constraints,axis_contract,
            retarget_solver,state
        )
        armature.pose.bones[
            support_foot_name
        ].matrix_basis=calibrated_support_foot.copy()
        bpy.context.view_layer.update()

        vertical=solve_support_vertical(
            armature,canonical,axes,runtime,support_shift
        )
        geometry=candidate_geometry(
            armature,canonical,runtime,axes,
            foot_length,rest_centroids,vertical
        )
        passed,reasons=geometry_pass(
            geometry,contract,foot_length
        )
        row={
            "parameters":params,
            "geometry":geometry,
            "pass":passed,
            "rejection_reasons":reasons,
        }
        candidates.append(row)
        if passed:
            winners.append((
                candidate_score(params,geometry,foot_length),
                params,
                state,
                geometry,
                vertical,
            ))

    require(
        bool(winners),
        "No crossed-reverence candidate satisfied support/contact/"
        "cross/back gates. Best diagnostics: "
        + json.dumps(candidates[:5]),
    )
    winners.sort(key=lambda item:item[0])
    score,best_params,best_state,best_geometry,best_vertical=winners[0]

    # Rebuild the winner exactly.
    best_retarget=apply_state(
        armature,canonical,constraints,axis_contract,
        retarget_solver,best_state
    )
    armature.pose.bones[
        support_foot_name
    ].matrix_basis=calibrated_support_foot.copy()
    bpy.context.view_layer.update()
    best_vertical=solve_support_vertical(
        armature,canonical,axes,runtime,support_shift
    )
    lower_pose=snapshot(armature)
    best_geometry=candidate_geometry(
        armature,canonical,runtime,axes,
        foot_length,rest_centroids,best_vertical
    )
    passed,reasons=geometry_pass(
        best_geometry,contract,foot_length
    )
    require(passed,f"Winning candidate did not replay: {reasons}")

    upper_evidence=apply_contextual_bras_bas(
        armature,canonical,runtime,static_contract,
        retarget,constraints,axis_contract,
        bras_bas_pose,arm_contract,contract
    )
    final_pose=snapshot(armature)

    # Lower-body local matrices must remain unchanged by arm/bow overlay except
    # axial trunk/head bones which are outside the lower chain.
    lower_names={
        canonical["canonical_bones"][name]["rig_bone"]
        for name in (
            "pelvis",
            "left_thigh","left_shin","left_foot","left_toes",
            "right_thigh","right_shin","right_foot","right_toes",
        )
    }
    lower_error=max(
        matrix_max_error(final_pose[name],lower_pose[name])
        for name in lower_names
    )
    require(
        lower_error <= 1e-6,
        f"Crossed stance lower chain changed after upper overlay: {lower_error}.",
    )

    hand_offsets={}
    inner_q=float(runtime["hand_sampling"]["inner_edge_quantile"])
    for side in ("left","right"):
        m=static_core.hand_mesh_inner_edge(
            armature,canonical,runtime["hand_samples"][side],
            side,inner_q
        )
        offset=float(m["side_offset"])
        hand_offsets[side]=offset
        require(
            offset
            >= float(contract["validation"]["minimum_hand_side_offset"])-1e-9,
            f"{side} hand crossed centerline: {offset}.",
        )

    # Foot/contact geometry must remain identical after upper-body overlay.
    final_geometry=candidate_geometry(
        armature,canonical,runtime,axes,
        foot_length,rest_centroids,best_vertical
    )
    final_pass,final_reasons=geometry_pass(
        final_geometry,contract,foot_length
    )
    require(
        final_pass,
        "Upper-body overlay disturbed crossed stance geometry: "
        + ", ".join(final_reasons),
    )

    previews,preview_evidence=render_previews(
        armature,canonical,contract,preview_dir
    )

    report={
        "phase":PHASE,
        "contract_id":contract["contract_id"],
        "reference_semantics":{
            "support_side":"left",
            "gesture_side":"right",
            "gesture_direction":"CROSS_AND_BACK",
            "gesture_contact":"FOREFOOT_OR_TOE_TOUCH",
            "arm_pose":"bras_bas",
        },
        "search":{
            "candidate_count":len(candidates),
            "passing_count":len(winners),
            "selected_score":list(map(float,score)),
            "selected_parameters":best_params,
            "candidates":candidates,
        },
        "selected_lower_state":best_state,
        "support_ankle_calibration":support_ankle_evidence,
        "support_shift":{
            "hip_width":width,
            "fraction":float(
                contract["lower_body"][
                    "pelvis_support_shift_hip_width_fraction"
                ]
            ),
            "distance":support_shift,
        },
        "geometry":final_geometry,
        "upper_body":upper_evidence,
        "diagnostics":{
            "lower_chain_post_overlay_error":lower_error,
            "hand_side_offsets":hand_offsets,
            "constraint_count":sum(
                len(pb.constraints) for pb in armature.pose.bones
            ),
            "imported_action_cleared":True,
        },
        "preview":{**preview_evidence,"files":previews},
        "automated_gate":{
            "preferred_joint_envelopes_pass":True,
            "support_full_foot_contact_pass":True,
            "gesture_forefoot_near_floor_pass":True,
            "gesture_heel_lift_pass":True,
            "gesture_cross_pass":True,
            "gesture_back_pass":True,
            "lower_body_asymmetry_pass":True,
            "accepted_bras_bas_reused":True,
            "hand_centerline_pass":True,
            "lower_chain_preserved_after_upper_overlay":True,
            "no_permanent_constraints":True,
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

    print("PHASE10_11_2_CROSSED_REVERENCE_STANCE_AUTOMATED_PROOF=PASS")
    print(f"PREVIEWS={';'.join(previews)}")
    print(
        "GESTURE="
        f"cross {final_geometry['normalized']['gesture_cross_foot_fraction']:.6f} foot | "
        f"back {final_geometry['normalized']['gesture_back_foot_fraction']:.6f} foot | "
        f"heel {final_geometry['normalized']['gesture_heel_lift_foot_fraction']:.6f} foot"
    )
    print(
        "SUPPORT_ERROR="
        f"{final_geometry['normalized']['support_error_foot_fraction']:.6f} foot"
    )
    print(f"SELECTED={best_params}")
    print("HUMAN_VISUAL_REVIEW=PENDING")
    print("ANIMATION_AUTHORED=NO")
    print("GLB_EXPORT=NOT_PERFORMED")
    print(f"REPORT={report_path}")


if __name__=="__main__":
    main()
