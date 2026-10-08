"""Planted bilateral contact with explicit quasistatic pelvis transfer."""
import copy,json,sys,math,hashlib,subprocess
from pathlib import Path
import numpy as np
from mathutils import Vector,Quaternion
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO/'tools/blender'),str(REPO/'tools/ballet_motion')]
from bbm_body_runtime_v1 import BodyRuntime,gate,surface_centroid
from render_bbm3_foot_v1 import apply_calibrated_basis
from distributed_turnout_v1 import derive_turnout,alignment_diagnostics
from weight_transfer_v1 import transfer_intent,weightbearing_roles,rotation_step_degrees
from support_balance_v1 import balance_diagnostics
from foot_semantics_v1 import foot_state,anatomical_plantar_from_canonical


def realize_transfer(body,state,offset,roles):
    for side in ('left','right'):
        knee=state['joint_dofs'][f'{side}_shin']['flexion_extension'];state['turnout'][side].update({'hip_external_rotation_deg':state['joint_dofs'][f'{side}_thigh']['internal_external_rotation'],'knee_flexion_deg':knee,'knee_external_rotation_deg':derive_turnout(body.constraints,state['joint_dofs'][f'{side}_thigh']['internal_external_rotation'],knee)['knee_external_rotation_deg']})
    # During search only left is guaranteed support. Right flat orientation
    # is solved independently; both contacts are strictly checked at output.
    try:result=body.realize(state,{'left':'SUPPORT','right':'SWING'})
    except ValueError as exc:
        foot=body.canonical['canonical_bones']['left_foot'];parent,rest=gate.static_core.canonical_parent_and_rest_local(body.rig,body.canonical,'left_foot');observed=gate.static_core.canonical_basis_from_rig_pose(body.rig.pose.bones[foot['rig_bone']],foot);delta=(parent@rest).transposed()@observed;raw=gate.static_core.extract_exact_ankle_plantar(delta)
        raise ValueError(str(exc)+'; observed left plantar='+str(raw)+' neutral='+str(body.neutral['left'])+' thigh='+str(state['joint_dofs']['left_thigh'])+' knee='+str(state['joint_dofs']['left_shin'])) from exc
    th=body.static['proof_thresholds'];solution=gate.static_core.solve_preferred_ankle_flat_contact(body.rig,body.canonical,body.constraints,'right_foot','right',body.up,body.runtime['anchors'],body.runtime['rest_heights'],body.q,th['full_foot_seed_up_alignment_min_dot'],th['full_foot_mesh_search_coarse_step_deg'],th['full_foot_mesh_search_refine_steps_deg']);foot=body.canonical['canonical_bones']['right_foot'];desired=solution['basis'];apply_calibrated_basis(body.rig,foot['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(foot,desired));decoded=anatomical_plantar_from_canonical(body.constraints,round(solution['plantar_dorsiflexion'],3),body.neutral['right']);foot_state(body.constraints,'FLAT',decoded['anatomical_plantar_deg'],0,solution['inversion_eversion'])
    toe=body.canonical['canonical_bones']['right_toes'];parent,rest=gate.static_core.canonical_parent_and_rest_local(body.rig,body.canonical,'right_toes');toe_target=(parent@rest).to_quaternion().normalized().to_matrix();apply_calibrated_basis(body.rig,toe['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(toe,toe_target))
    error=max(gate.matrix_max_error(gate.static_core.canonical_basis_from_rig_pose(body.rig.pose.bones[foot['rig_bone']],foot),desired),gate.matrix_max_error(gate.static_core.canonical_basis_from_rig_pose(body.rig.pose.bones[toe['rig_bone']],toe),toe_target))
    if decoded['status']!='PASS' or error>body.axis['thresholds']['hierarchy_reconstruction_max_error']:raise RuntimeError('Right anatomical/matrix proof failed')
    translation=body.up*result['root_translation'][2]+body.left*offset;gate.static_core.set_root_translation_armature_space(body.rig,body.canonical['canonical_bones']['pelvis']['rig_bone'],translation)
    trunk={}
    if True:
        fraction=offset/.08
        names=[body.canonical['canonical_bones'][n]['rig_bone'] for n in ('spine_lower','spine_mid')]+['Chest','Clavicle_L','Clavicle_R','Upper_Arm_L','Upper_Arm_R','Lower_Arm_L','Lower_Arm_R','Hand_L','Hand_R','Head']
        original={n:body.rig.pose.bones[n].matrix.to_quaternion().normalized().to_matrix() for n in names}
        for j,n in enumerate(names):
            share=(j+1)/3 if j<2 else 1
            rotation=Quaternion(body.left,math.radians(-7.5*fraction*share))@Quaternion(body.front,math.radians(-2.5*fraction*share))
            apply_calibrated_basis(body.rig,n,rotation.to_matrix()@original[n])
        chest=body.rig.pose.bones['Chest'];tilt=math.degrees((chest.tail-chest.head).angle(body.up))
        policy=next(c for c in body.grammar['poses']['plie']['checks'] if c.get('name')=='trunk_tilt_deg')
        if tilt>policy['max']:raise RuntimeError('Existing trunk tilt gate failed')
        trunk={'backward_transport_deg':7.5*fraction,'lateral_transport_deg':2.5*fraction,'observed_chest_tilt_deg':tilt,'existing_plie_limit_deg':policy['max'],'spine_distribution':[1/3,2/3,1],'upper_carriage_transport':'shared world rotation preserves local arm/head relationship'}
    heights=gate.static_core.contact_heights(body.rig,body.runtime['anchors'],body.up,body.q);errors={s:{r:heights[s][r]-body.runtime['rest_heights'][s][r] for r in ('rear','fore')} for s in ('left','right')};maximum=max(abs(e) for v in errors.values() for e in v.values())
    centers={s:sum(gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][s]['rear']),Vector())/len(body.runtime['anchors'][s]['rear']) for s in ('left','right')}
    fore_centers={s:sum(gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][s]['fore']),Vector())/len(body.runtime['anchors'][s]['fore']) for s in ('left','right')}
    points={}
    for side in ('left','right'):
        selected=[]
        for region in ('rear','fore'):
            ps=sorted(gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][side][region]),key=lambda p:p.dot(body.up));selected+=ps[:max(3,int(len(ps)*body.q))]
        points[side]=[(p.dot(body.left),p.dot(body.front)) for p in selected]
    com,area=surface_centroid(body.rig);balance=balance_diagnostics(points,(com.dot(body.left),com.dot(body.front)),weightbearing_roles(roles));balance['support_roles']=roles
    root=body.rig.pose.bones[body.canonical['canonical_bones']['pelvis']['rig_bone']];actual=root.head-root.bone.head_local;root_error=max(abs(actual.dot(body.left)-offset),abs(actual.dot(body.front)))
    if root_error>1e-7:raise RuntimeError('Unintended root displacement')
    alignment={}
    for side in ('left','right'):
        shin=body.canonical['canonical_bones'][f'{side}_shin'];toe=body.canonical['canonical_bones'][f'{side}_toes'];heading=gate.static_core.canonical_basis_from_rig_pose(body.rig.pose.bones[shin['rig_bone']],shin).col[2];ray=body.rig.pose.bones[toe['rig_bone']].tail-body.rig.pose.bones[toe['rig_bone']].head;alignment[side]=alignment_diagnostics(body.constraints,list(heading),list(ray),list(body.front),list(body.up))
    return {'trunk_transport':trunk,'balance':balance,'contact_errors':errors,'contact_max_abs':maximum,'rear_centers':{s:list(c) for s,c in centers.items()},'fore_centers':{s:list(c) for s,c in fore_centers.items()},'root_intent_left':offset,'root_intent_error':root_error,'alignment':alignment,'right_foot_proof':{'anatomical':decoded,'matrix_error':error},'canonical_state':copy.deepcopy(state),'wrist':gate.validate_hand_axial_continuity(body.rig,body.canonical,body.constraints,body.visual)}
