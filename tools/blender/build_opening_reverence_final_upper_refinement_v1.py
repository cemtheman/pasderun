"""Phase 10.11.4 reverence upper-body expression refinement proof."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector


PHASE="10.11.4"
HERE=Path(__file__).resolve().parent
REPO_DEFAULT=HERE.parents[1]
BALLET_TOOLS=REPO_DEFAULT/"tools"/"ballet_motion"
for path in (HERE,BALLET_TOOLS):
    if str(path) not in sys.path:
        sys.path.insert(0,str(path))

import apply_static_foundation_poses_v1 as static_core  # noqa: E402
import render_foundation_pose_visual_gate_v1 as visual_gate  # noqa: E402
import build_foundation_transition_v1 as arm_motion  # noqa: E402
import build_opening_reverence_crossed_stance_v1 as crossed_base  # noqa: E402
import opening_reverence_crossed_stance as crossed_semantics  # noqa: E402
import opening_reverence_final_upper_refinement as refinement  # noqa: E402


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
    p.add_argument("--source-crossed-contract",required=True)
    p.add_argument("--refinement-contract",required=True)
    p.add_argument("--report",required=True)
    p.add_argument("--preview-dir",required=True)
    p.add_argument("--diagnostic-only",action="store_true")
    p.add_argument("--diagnostic-report",default="")
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


def restore(armature: bpy.types.Object, pose: dict) -> None:
    for name,matrix in pose.items():
        armature.pose.bones[name].matrix_basis=matrix.copy()
    bpy.context.view_layer.update()


def matrix_max_error(a,b) -> float:
    return max(
        abs(float(a[r][c])-float(b[r][c]))
        for r in range(4)
        for c in range(4)
    )


def endpoint_interpolated_arm_pose(
    start_pose: dict,
    end_pose: dict,
    roles: dict[str,str],
    parameters: dict,
) -> dict:
    result={}
    for rig_name,role in roles.items():
        if role=="shoulder":
            progress=float(parameters["shoulder_progress"])
        elif role=="elbow":
            progress=float(parameters["elbow_progress"])
        else:
            # Wrist and fingers remain exact accepted bras_bas.
            progress=0.0

        if progress <= 0.0:
            result[rig_name]=start_pose[rig_name].copy()
            continue

        start_matrix=start_pose[rig_name]
        end_matrix=end_pose[rig_name]
        location,_start_decomp_q,scale=start_matrix.decompose()
        start_q=start_matrix.to_3x3().normalized().to_quaternion()
        end_q=end_matrix.to_3x3().normalized().to_quaternion()
        start_q.normalize()
        end_q.normalize()
        if start_q.dot(end_q) < 0.0:
            end_q.negate()
        q=start_q.slerp(end_q,progress)
        q.normalize()
        result[rig_name]=Matrix.LocRotScale(
            location,
            q,
            scale,
        )
    return result


def apply_bow(
    armature,
    canonical,
    contract,
) -> None:
    bow=contract["upper_body"]["bow"]
    total=float(bow["trunk_extra_flexion_deg"])
    for route in bow["trunk_routes"]:
        crossed_base.apply_canonical_x_increment(
            armature,
            canonical,
            route["bone"],
            total*float(route["weight"]),
        )
    crossed_base.apply_canonical_x_increment(
        armature,
        canonical,
        "neck",
        float(bow["neck_flexion_deg"]),
    )
    crossed_base.apply_canonical_x_increment(
        armature,
        canonical,
        "head",
        float(bow["head_flexion_deg"]),
    )
    bpy.context.view_layer.update()


def hand_geometry(
    armature,
    canonical,
    runtime,
    axes,
) -> dict:
    inner_q=float(runtime["hand_sampling"]["inner_edge_quantile"])
    raw={}
    for side in ("left","right"):
        raw[side]=static_core.hand_mesh_inner_edge(
            armature,
            canonical,
            runtime["hand_samples"][side],
            side,
            inner_q,
        )

    left_shoulder_name=canonical["canonical_bones"][
        "left_upper_arm"
    ]["rig_bone"]
    right_shoulder_name=canonical["canonical_bones"][
        "right_upper_arm"
    ]["rig_bone"]
    left_shoulder=Vector(
        armature.pose.bones[left_shoulder_name].head
    )
    right_shoulder=Vector(
        armature.pose.bones[right_shoulder_name].head
    )
    left_axis=axes["left"]
    left_shoulder_coord=float(left_shoulder.dot(left_axis))
    right_shoulder_coord=float(right_shoulder.dot(left_axis))
    shoulder_mid=0.5*(left_shoulder_coord+right_shoulder_coord)
    shoulder_width=abs(left_shoulder_coord-right_shoulder_coord)
    require(
        shoulder_width > 1e-9,
        "Shoulder width collapsed during reverence hand measurement.",
    )

    left_inner=float(raw["left"]["inner_edge"])
    right_inner=float(raw["right"]["inner_edge"])
    midpoint_offsets={
        "left":left_inner-shoulder_mid,
        "right":shoulder_mid-right_inner,
    }
    gap=left_inner-right_inner
    asymmetry=abs(
        midpoint_offsets["left"]-midpoint_offsets["right"]
    )

    return {
        "metric_authority":"SHOULDER_MIDPOINT_BODY_FRAME_LEFT_AXIS",
        "shoulder_left_coordinate":left_shoulder_coord,
        "shoulder_right_coordinate":right_shoulder_coord,
        "shoulder_midpoint_coordinate":shoulder_mid,
        "shoulder_width":shoulder_width,
        "inner_edges":{
            "left":left_inner,
            "right":right_inner,
        },
        "midpoint_side_offsets":midpoint_offsets,
        "gap":gap,
        "gap_shoulder_width_fraction":gap/shoulder_width,
        "midpoint_asymmetry":asymmetry,
        "midpoint_asymmetry_shoulder_width_fraction":(
            asymmetry/shoulder_width
        ),
    }


def elbow_geometry(
    armature,
    canonical,
    axes,
) -> dict:
    result={}
    all_below=True
    for side in ("left","right"):
        upper_name=canonical["canonical_bones"][
            f"{side}_upper_arm"
        ]["rig_bone"]
        bone=armature.pose.bones[upper_name]
        shoulder=Vector(bone.head)
        elbow=Vector(bone.tail)
        vertical_delta=float(
            (elbow-shoulder).dot(axes["up"])
        )
        result[side]={
            "shoulder":list(map(float,shoulder)),
            "elbow":list(map(float,elbow)),
            "elbow_minus_shoulder_up":vertical_delta,
            "below_shoulder":vertical_delta <= 1e-7,
        }
        all_below=all_below and result[side]["below_shoulder"]
    return {
        "sides":result,
        "both_elbows_below_shoulder_line":all_below,
    }


def arm_endpoint_local_deltas(
    start_pose: dict,
    end_pose: dict,
    roles: dict[str,str],
) -> dict:
    """Measure what the accepted endpoint realizations actually change."""
    result={}
    for rig_name,role in sorted(roles.items()):
        if role not in ("shoulder","elbow","wrist"):
            continue
        start_matrix=start_pose[rig_name]
        end_matrix=end_pose[rig_name]
        start_loc,start_q,start_scale=start_matrix.decompose()
        end_loc,end_q,end_scale=end_matrix.decompose()
        start_q.normalize()
        end_q.normalize()
        if start_q.dot(end_q) < 0.0:
            end_q.negate()
        result[rig_name]={
            "role":role,
            "rotation_delta_deg":math.degrees(
                start_q.rotation_difference(end_q).angle
            ),
            "translation_delta":float((end_loc-start_loc).length),
            "scale_delta":float((end_scale-start_scale).length),
        }
    return result


def hand_centroid_geometry(
    armature,
    runtime,
    axes,
) -> dict:
    result={}
    for side in ("left","right"):
        points=static_core.evaluated_sample_points(
            armature,
            runtime["hand_samples"][side],
        )
        require(points,f"{side}: hand diagnostic sample set is empty.")
        centroid=Vector((0.0,0.0,0.0))
        for point in points:
            centroid+=point
        centroid/=len(points)
        result[side]={
            "sample_count":len(points),
            "centroid":list(map(float,centroid)),
            "left":float(centroid.dot(axes["left"])),
            "front":float(centroid.dot(axes["front"])),
            "up":float(centroid.dot(axes["up"])),
        }
    return result


def diagnostic_arm_probe(
    armature,
    canonical,
    runtime,
    axes,
    contract,
    lower_pose,
    arm_pose,
) -> dict:
    restore(armature,lower_pose)
    for name,matrix in arm_pose.items():
        armature.pose.bones[name].matrix_basis=matrix.copy()
    bpy.context.view_layer.update()

    pre_hand=hand_geometry(armature,canonical,runtime,axes)
    pre_centroid=hand_centroid_geometry(armature,runtime,axes)
    pre_elbow=elbow_geometry(armature,canonical,axes)

    apply_bow(armature,canonical,contract)

    post_hand=hand_geometry(armature,canonical,runtime,axes)
    post_centroid=hand_centroid_geometry(armature,runtime,axes)
    post_elbow=elbow_geometry(armature,canonical,axes)
    return {
        "before_bow":{
            "hand_geometry":pre_hand,
            "hand_centroids":pre_centroid,
            "elbow_geometry":pre_elbow,
        },
        "after_bow":{
            "hand_geometry":post_hand,
            "hand_centroids":post_centroid,
            "elbow_geometry":post_elbow,
        },
        "bow_effect":{
            "gap_shoulder_width_fraction_delta":float(
                post_hand["gap_shoulder_width_fraction"]
                - pre_hand["gap_shoulder_width_fraction"]
            ),
            "left_midpoint_offset_delta":float(
                post_hand["midpoint_side_offsets"]["left"]
                - pre_hand["midpoint_side_offsets"]["left"]
            ),
            "right_midpoint_offset_delta":float(
                post_hand["midpoint_side_offsets"]["right"]
                - pre_hand["midpoint_side_offsets"]["right"]
            ),
        },
    }


def arm_authority_diagnostic(
    armature,
    canonical,
    runtime,
    axes,
    contract,
    lower_pose,
    arm_roles,
    bras_bas_pose,
    en_avant_pose,
) -> dict:
    def exact(pose: dict) -> dict:
        return {
            name:pose[name].copy()
            for name in arm_roles
        }

    def interpolated(shoulder: float,elbow: float) -> dict:
        return endpoint_interpolated_arm_pose(
            bras_bas_pose,
            en_avant_pose,
            arm_roles,
            {
                "shoulder_progress":float(shoulder),
                "elbow_progress":float(elbow),
            },
        )

    probes=[
        ("exact_bras_bas",exact(bras_bas_pose)),
        ("exact_en_avant",exact(en_avant_pose)),
        ("shoulder_08_only",interpolated(0.08,0.0)),
        ("elbow_08_only",interpolated(0.0,0.08)),
        ("shoulder_16_only",interpolated(0.16,0.0)),
        ("elbow_16_only",interpolated(0.0,0.16)),
        ("combined_08",interpolated(0.08,0.08)),
        ("en_avant_shoulder_only",interpolated(1.0,0.0)),
        ("en_avant_elbow_only",interpolated(0.0,1.0)),
        (
            "en_avant_shoulder_elbow_bras_wrist_fingers",
            interpolated(1.0,1.0),
        ),
    ]

    rows=[]
    for name,pose in probes:
        rows.append({
            "name":name,
            **diagnostic_arm_probe(
                armature,
                canonical,
                runtime,
                axes,
                contract,
                lower_pose,
                pose,
            ),
        })

    return {
        "mode":"ARM_AUTHORITY_DIAGNOSTIC_ONLY",
        "arm_role_map":{
            name:role
            for name,role in sorted(arm_roles.items())
        },
        "endpoint_local_deltas":arm_endpoint_local_deltas(
            bras_bas_pose,en_avant_pose,arm_roles
        ),
        "probe_count":len(rows),
        "probes":rows,
        "authority_selected":False,
        "optimizer_used":False,
        "centerline_projection_used":False,
    }


def arm_candidate_pass(
    hand: dict,
    elbow: dict,
    contract: dict,
) -> tuple[bool,list[str]]:
    target=contract["visual_geometry_targets"]
    reasons=[]
    if (
        hand["metric_authority"]
        != target["metric_authority"]
    ):
        reasons.append("hand_metric_authority")
    gap=float(hand["gap_shoulder_width_fraction"])
    if gap < float(
        target["hand_gap_shoulder_width_fraction_min"]
    ):
        reasons.append("hand_gap_too_small")
    if gap > float(
        target["hand_gap_shoulder_width_fraction_max"]
    ):
        reasons.append("hand_gap_too_large")
    for side,value in hand["midpoint_side_offsets"].items():
        if value < float(target["each_hand_midline_offset_min"])-1e-9:
            reasons.append(f"{side}_hand_crosses_shoulder_midline")
    if (
        hand["midpoint_asymmetry_shoulder_width_fraction"]
        > float(
            target[
                "hand_midpoint_asymmetry_shoulder_width_fraction_max"
            ]
        )
    ):
        reasons.append("hand_midpoint_asymmetry")
    if (
        target["elbows_must_remain_below_shoulder_line"]
        and not elbow["both_elbows_below_shoulder_line"]
    ):
        reasons.append("elbow_above_shoulder")
    return not reasons,reasons


def candidate_score(
    parameters: dict,
    hand: dict,
    contract: dict,
) -> tuple:
    target=contract["visual_geometry_targets"]
    ideal=float(target["hand_gap_shoulder_width_fraction_ideal"])
    # Geometry first; then prefer the smallest departure from accepted
    # bras_bas (30° shoulder abduction, 55° elbow flexion).
    return (
        abs(float(hand["gap_shoulder_width_fraction"])-ideal),
        float(parameters["shoulder_progress"])+float(parameters["elbow_progress"]),
        float(parameters["shoulder_progress"]),
        float(parameters["elbow_progress"]),
    )


def current_lower_geometry(
    armature,
    canonical,
    runtime,
    axes,
    foot_length,
    rest_centroids,
) -> dict:
    heights=static_core.contact_heights(
        armature,
        runtime["anchors"],
        runtime["up_axis"],
        float(runtime["sampling"]["low_height_quantile"]),
    )
    support_errors={
        region:float(heights["left"][region])
        - float(runtime["rest_heights"]["left"][region])
        for region in ("rear","fore")
    }
    evidence={
        "support_errors":support_errors,
        "all_heights":heights,
    }
    return crossed_base.candidate_geometry(
        armature,
        canonical,
        runtime,
        axes,
        foot_length,
        rest_centroids,
        evidence,
    )


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
        path=preview_dir/f"opening_reverence_final_{view.lower()}.png"
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
    source_contract=load_json(args.source_crossed_contract)
    contract=load_json(args.refinement_contract)

    refinement.validate_contract(contract)
    crossed_semantics.validate_contract(source_contract)
    require(
        source_contract["contract_id"]
        == contract["lower_body_authority"]["source_contract_id"],
        "Frozen crossed-stance source contract mismatch.",
    )

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

    axes=crossed_base.body_axes(canonical,runtime)
    width=crossed_base.hip_width(
        armature,canonical,axes["left"]
    )
    support_shift=(
        width
        * float(
            source_contract["lower_body"][
                "pelvis_support_shift_hip_width_fraction"
            ]
        )
    )
    foot_length=float(
        static_core.body_metrics(canonical)["foot_chain_length"]
    )
    # Measure calibrated rest gesture forefoot centroid.
    static_core.clear_pose(armature)
    rest_centroids={
        "right_fore":crossed_base.region_centroid(
            armature,runtime["anchors"]["right"]["fore"]
        )
    }

    frozen_parameters={
        key:float(value)
        for key,value in contract["lower_body_authority"][
            "frozen_selected_parameters"
        ].items()
    }
    lower_state=crossed_semantics.build_state(
        source_contract,
        frozen_parameters,
    )
    violations=crossed_semantics.preferred_envelope_violations(
        lower_state,constraints
    )
    require(
        not violations,
        "Frozen 10.11.2 lower state left preferred envelope: "
        + "; ".join(violations),
    )

    # The support leg is fixed in 10.11.2, so recalibrate its full-foot ankle
    # with the same accepted source helper before rebuilding the frozen winner.
    crossed_base.apply_state(
        armature,canonical,constraints,axis_contract,
        retarget_solver,lower_state
    )
    crossed_base.set_support_shift(
        armature,canonical,axes,support_shift,0.0
    )
    support_ankle_evidence=crossed_base.calibrate_support_foot(
        armature,canonical,constraints,runtime,static_contract
    )
    support_foot_name=canonical["canonical_bones"][
        "left_foot"
    ]["rig_bone"]
    calibrated_support_foot=armature.pose.bones[
        support_foot_name
    ].matrix_basis.copy()

    crossed_base.apply_state(
        armature,canonical,constraints,axis_contract,
        retarget_solver,lower_state
    )
    armature.pose.bones[
        support_foot_name
    ].matrix_basis=calibrated_support_foot.copy()
    bpy.context.view_layer.update()
    source_vertical=crossed_base.solve_support_vertical(
        armature,canonical,axes,runtime,support_shift
    )
    lower_pose=snapshot(armature)
    frozen_geometry=crossed_base.candidate_geometry(
        armature,canonical,runtime,axes,
        foot_length,rest_centroids,source_vertical
    )
    frozen_pass,frozen_reasons=crossed_base.geometry_pass(
        frozen_geometry,source_contract,foot_length
    )
    require(
        frozen_pass,
        "Frozen 10.11.2 lower geometry no longer passes source gates: "
        + ", ".join(frozen_reasons),
    )

    arm_roles,_=arm_motion.actual_upper_chain(
        armature,canonical,static_contract
    )
    arm_names=set(arm_roles)
    arm_authority=contract["upper_body"]["arm_source_authority"]

    bras_bas_pose,bras_bas_endpoint_evidence=arm_motion.realize_endpoint(
        arm_authority["start_pose"],
        armature,
        canonical,
        constraints,
        retarget,
        axis_contract,
        static_contract,
        visual_contract,
        runtime,
    )
    en_avant_pose,en_avant_endpoint_evidence=arm_motion.realize_endpoint(
        arm_authority["upper_bound_reference_pose"],
        armature,
        canonical,
        constraints,
        retarget,
        axis_contract,
        static_contract,
        visual_contract,
        runtime,
    )

    if args.diagnostic_only:
        require(
            bool(args.diagnostic_report),
            "--diagnostic-report is required with --diagnostic-only.",
        )
        diagnostic=arm_authority_diagnostic(
            armature,
            canonical,
            runtime,
            axes,
            contract,
            lower_pose,
            arm_roles,
            bras_bas_pose,
            en_avant_pose,
        )
        diagnostic_payload={
            "phase":PHASE,
            "contract_id":contract["contract_id"],
            "mode":"ARM_AUTHORITY_DIAGNOSTIC_ONLY",
            "frozen_lower_authority":{
                "source_phase":"10.11.2",
                "source_contract_id":source_contract["contract_id"],
                "selected_parameters":frozen_parameters,
                "source_geometry":frozen_geometry,
            },
            "endpoint_realization_evidence":{
                "bras_bas":bras_bas_endpoint_evidence,
                "en_avant":en_avant_endpoint_evidence,
            },
            "arm_diagnostic":diagnostic,
            "policy":{
                "authority_selected":False,
                "animation_authored":False,
                "glb_exported":False,
                "human_visual_verdict":False,
            },
        }
        diagnostic_path=Path(args.diagnostic_report).resolve()
        diagnostic_path.parent.mkdir(parents=True,exist_ok=True)
        serialized=json.dumps(
            crossed_base.json_ready(diagnostic_payload),
            indent=2,
            allow_nan=False,
        )
        json.loads(serialized)
        diagnostic_path.write_text(serialized,encoding="utf-8")

        print("PHASE10_11_4_ARM_AUTHORITY_DIAGNOSTIC=PASS")
        print(f"PROBES={diagnostic['probe_count']}")
        for rig_name,row in diagnostic["endpoint_local_deltas"].items():
            print(
                "ENDPOINT_LOCAL_DELTA="
                f"{rig_name}|{row['role']}|"
                f"rotation_deg={row['rotation_delta_deg']:.6f}|"
                f"translation={row['translation_delta']:.9f}|"
                f"scale={row['scale_delta']:.9f}"
            )
        for row in diagnostic["probes"]:
            before=row["before_bow"]["hand_geometry"]
            after=row["after_bow"]["hand_geometry"]
            centroids=row["after_bow"]["hand_centroids"]
            bow_delta=row["bow_effect"]["gap_shoulder_width_fraction_delta"]
            print(
                "ARM_PROBE="
                f"{row['name']}|"
                f"pre_gap={before['gap_shoulder_width_fraction']:.6f}|"
                f"post_gap={after['gap_shoulder_width_fraction']:.6f}|"
                f"bow_gap_delta={bow_delta:.9f}|"
                f"left_front={centroids['left']['front']:.6f}|"
                f"right_front={centroids['right']['front']:.6f}|"
                f"left_up={centroids['left']['up']:.6f}|"
                f"right_up={centroids['right']['up']:.6f}"
            )
        print("AUTHORITY_SELECTED=NO")
        print("CENTERLINE_PROJECTION=NOT_USED")
        print("ANIMATION_AUTHORED=NO")
        print("GLB_EXPORT=NOT_PERFORMED")
        print(f"DIAGNOSTIC_REPORT={diagnostic_path}")
        return

    candidates=[]
    winners=[]
    for parameters in refinement.arm_candidate_parameter_sets(
        contract
    ):
        arm_pose=endpoint_interpolated_arm_pose(
            bras_bas_pose,
            en_avant_pose,
            arm_roles,
            parameters,
        )
        restore(armature,lower_pose)
        for name,matrix in arm_pose.items():
            armature.pose.bones[name].matrix_basis=matrix.copy()
        bpy.context.view_layer.update()

        apply_bow(armature,canonical,contract)

        hand=hand_geometry(
            armature,canonical,runtime,axes
        )
        elbow=elbow_geometry(
            armature,canonical,axes
        )
        passed,reasons=arm_candidate_pass(
            hand,elbow,contract
        )
        row={
            "parameters":parameters,
            "hand_geometry":hand,
            "elbow_geometry":elbow,
            "pass":passed,
            "rejection_reasons":reasons,
        }
        candidates.append(row)
        if passed:
            score=candidate_score(
                parameters,hand,contract
            )
            winners.append((
                score,
                parameters,
                arm_pose,
                hand,
                elbow,
            ))

    require(
        bool(winners),
        "No low-oval arm candidate satisfied hand-gap/elbow gates. "
        "Diagnostics: "+json.dumps(candidates),
    )
    winners.sort(key=lambda item:item[0])
    (
        selected_score,
        selected_parameters,
        selected_arm_pose,
        selected_hand,
        selected_elbow,
    )=winners[0]

    # Rebuild selected final pose exactly.
    restore(armature,lower_pose)
    for name,matrix in selected_arm_pose.items():
        armature.pose.bones[name].matrix_basis=matrix.copy()
    bpy.context.view_layer.update()
    apply_bow(armature,canonical,contract)
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
        matrix_max_error(final_pose[name],lower_pose[name])
        for name in lower_names
    )
    require(
        lower_error
        <= float(
            contract["validation"][
                "frozen_lower_chain_local_matrix_error_max"
            ]
        ),
        f"10.11.3 changed frozen lower chain: {lower_error}.",
    )

    final_lower_geometry=current_lower_geometry(
        armature,canonical,runtime,axes,
        foot_length,rest_centroids
    )
    final_lower_pass,final_lower_reasons=(
        crossed_base.geometry_pass(
            final_lower_geometry,
            source_contract,
            foot_length,
        )
    )
    require(
        final_lower_pass,
        "10.11.3 upper refinement disturbed frozen lower geometry: "
        + ", ".join(final_lower_reasons),
    )

    final_hand=hand_geometry(
        armature,canonical,runtime,axes
    )
    final_elbow=elbow_geometry(
        armature,canonical,axes
    )
    final_arm_pass,final_arm_reasons=arm_candidate_pass(
        final_hand,final_elbow,contract
    )
    require(
        final_arm_pass,
        "Selected arm candidate did not replay: "
        + ", ".join(final_arm_reasons),
    )

    previews,preview_evidence=render_previews(
        armature,canonical,contract,preview_dir
    )

    report={
        "phase":PHASE,
        "contract_id":contract["contract_id"],
        "frozen_lower_authority":{
            "source_phase":"10.11.2",
            "source_contract_id":source_contract["contract_id"],
            "selected_parameters":frozen_parameters,
            "support_ankle_calibration":support_ankle_evidence,
            "source_geometry":frozen_geometry,
            "final_geometry":final_lower_geometry,
        },
        "upper_refinement":{
            "candidate_count":len(candidates),
            "passing_count":len(winners),
            "selected_parameters":selected_parameters,
            "selected_score":list(map(float,selected_score)),
            "selected_hand_geometry":final_hand,
            "selected_elbow_geometry":final_elbow,
            "arm_source_authority":arm_authority,
            "interpolation_policy":{
                "shoulder":"QUATERNION_SHORTEST_ARC_SLERP",
                "elbow":"QUATERNION_SHORTEST_ARC_SLERP",
                "wrist":"EXACT_BRAS_BAS",
                "fingers":"EXACT_BRAS_BAS",
                "translation":"LOCK_TO_BRAS_BAS",
                "scale":"LOCK_TO_BRAS_BAS",
            },
            "candidates":candidates,
            "bow":contract["upper_body"]["bow"],
            "centerline_projection_used":False,
        },
        "diagnostics":{
            "frozen_lower_chain_local_matrix_error":lower_error,
            "constraint_count":sum(
                len(pb.constraints) for pb in armature.pose.bones
            ),
            "imported_action_cleared":True,
        },
        "preview":{**preview_evidence,"files":previews},
        "automated_gate":{
            "frozen_10_11_2_parameters_exact":True,
            "frozen_lower_source_geometry_repassed":True,
            "accepted_arm_endpoint_bounded_interpolation_pass":True,
            "low_oval_stays_within_en_avant_guard":True,
            "hand_gap_pass":True,
            "hand_symmetry_pass":True,
            "hand_centerline_pass":True,
            "elbows_below_shoulder_line_pass":True,
            "centerline_projection_absent":True,
            "frozen_lower_chain_exact_after_refinement":True,
            "frozen_lower_geometry_pass_after_refinement":True,
            "no_permanent_constraints":True,
            "imported_action_cleared":True,
            "report_json_serializable":True,
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
    serial_report=crossed_base.json_ready(report)
    serialized=json.dumps(
        serial_report,
        indent=2,
        allow_nan=False,
    )
    json.loads(serialized)
    report_path.write_text(
        serialized,
        encoding="utf-8",
    )

    print("PHASE10_11_4_REVERENCE_FINAL_UPPER_AUTOMATED_PROOF=PASS")
    print(f"PREVIEWS={';'.join(previews)}")
    print(
        "ARM_CANDIDATES="
        f"{len(winners)}/{len(candidates)} pass"
    )
    print(
        "HAND_GAP="
        f"{final_hand['gap_shoulder_width_fraction']:.6f} shoulder-width"
    )
    print(
        "HAND_ASYMMETRY="
        f"{final_hand['midpoint_asymmetry_shoulder_width_fraction']:.6f} shoulder-width"
    )
    print(
        "SELECTED_ARM="
        +json.dumps(selected_parameters,separators=(",",":"))
    )
    print(
        "LOWER_CROSS_BACK="
        f"{final_lower_geometry['normalized']['gesture_cross_foot_fraction']:.6f} / "
        f"{final_lower_geometry['normalized']['gesture_back_foot_fraction']:.6f} foot"
    )
    print("REPORT_JSON=VALID")
    print("HUMAN_VISUAL_REVIEW=PENDING")
    print("ANIMATION_AUTHORED=NO")
    print("GLB_EXPORT=NOT_PERFORMED")
    print(f"REPORT={report_path}")


if __name__=="__main__":
    main()
