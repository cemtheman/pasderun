"""Isolated turnout fixtures with measured alignment and unchanged contact gates."""
import copy,json,sys,math,hashlib,subprocess
from pathlib import Path
import bpy
from mathutils import Vector,Matrix,Quaternion
REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'tools/blender'),str(REPO/'tools/ballet_motion')]
import render_foundation_pose_visual_gate_v1 as gate
from distributed_turnout_v1 import derive_turnout,alignment_diagnostics
from calibrated_rig_retarget import retarget_pose_solution
from canonical_pose_solver import _check_preferred_joint_envelope
from ballet_pose_validators import validate_pose


def main():
    out=REPO/'build/visual_validation/BBM-2';out.mkdir(parents=True,exist_ok=True)
    load=lambda p:json.loads(p.read_text())
    base=REPO/'build/phase10_6';asset=REPO/'assets/ballet_motion'
    canonical=load(base/'low_poly_girl_canonical_ballet_profile_v1.json');constraints=load(base/'low_poly_girl_anatomical_constraint_profile_v1.json')
    poses=load(base/'low_poly_girl_canonical_pose_solver_v1.json');retarget=load(base/'low_poly_girl_calibrated_rig_retarget_v1.json')
    axis=load(asset/'retarget_axis_contract_v1.json');static=load(asset/'static_rig_application_contract_v1.json');visual=load(asset/'foundation_pose_visual_gate_v1.json');grammar=load(base/'low_poly_girl_ballet_pose_grammar_profile_v1.json')
    source=REPO/canonical['source']['path']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=canonical['source']['sha256']:raise RuntimeError('Source GLB changed')
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source))
    rig=gate.static_core.find_armature(canonical['source']['armature'])
    for obj in bpy.context.scene.objects:
        if obj.animation_data:obj.animation_data_clear()
    runtime=gate.prepare_contact_runtime(rig,canonical,static)
    frame=canonical['body_frame']['declared_axes_armature_local'];up=Vector(frame['up']);front=Vector(frame['front']);left=Vector(frame['left'])
    scene=bpy.context.scene;gate.configure_workbench(scene,420);camera,center,scale=gate.create_camera(rig,canonical)
    upper_report=load(REPO/'build/visual_validation/BBM-1/elbow-path/report.json')
    if upper_report['ai_visual_status']!='AI_VISUAL_PASS':raise RuntimeError('BBM-1 must pass before BBM-2')
    upper=upper_report['samples'][0]['orientations_wxyz']
    results={};failures=[]
    def heel_inner_gap():
        rear={side:gate.static_core.evaluated_sample_points(rig,runtime['anchors'][side]['rear']) for side in ('left','right')}
        return min(v.dot(left) for v in rear['left'])-max(v.dot(left) for v in rear['right'])
    for variant in ('baseline','candidate'):
        cells=out/variant;cells.mkdir(exist_ok=True)
        for row,pose in enumerate(('first','fifth','plie')):
            original='bras_bas' if pose=='first' else pose
            solution=copy.deepcopy(poses['solutions'][original]);state=solution['state'];state['pose']=pose;solution['pose']=pose
            if pose=='first' and variant=='candidate':
                lower=poses['solutions']['fifth']['state']
                state['contacts']=copy.deepcopy(lower['contacts']);state['turnout']=copy.deepcopy(lower['turnout'])
                state['joint_dofs'].update(copy.deepcopy(lower['joint_dofs']))
                for side in ('left','right'):
                    state['joint_dofs'][f'{side}_thigh']['abduction_adduction']=-6
                    state['joint_dofs'][f'{side}_shin']['flexion_extension']=0
                    state['turnout'][side]['knee_flexion_deg']=0
            if variant=='candidate' and pose=='fifth':
                for side in ('left','right'):
                    state['joint_dofs'][f'{side}_thigh'].update({'flexion_extension':6 if side=='left' else -6,'abduction_adduction':-7.5,'internal_external_rotation':60})
                    state['joint_dofs'][f'{side}_shin']['flexion_extension']=0
                    state['turnout'][side].update({'hip_external_rotation_deg':60,'knee_flexion_deg':0})
            authority={}
            if variant=='candidate':
                for side,request in state.get('turnout',{}).items():
                    result=derive_turnout(constraints,request['hip_external_rotation_deg'],request['knee_flexion_deg'])
                    authority[side]=result
                    if result['status']!='PASS':raise RuntimeError(f'Turnout envelope failed {pose} {side}')
                    request['knee_external_rotation_deg']=result['knee_external_rotation_deg']
            violations=_check_preferred_joint_envelope(state,constraints)
            if violations:raise RuntimeError(str(violations))
            # Existing upper grammar for the new first fixture, existing lower grammar for fifth/plie.
            solution['validation']=validate_pose(state,grammar['poses'][original],constraints,canonical)
            if solution['validation']['status']!='PASS':raise RuntimeError(str(solution['validation']))
            if variant=='candidate' and pose in ('first','plie'):
                low,high=(-6.0,0.0) if pose=='first' else (6.0,20.0)
                desired_gap=runtime['metrics']['foot_chain_length']*.005
                for iteration in range(13):
                    adduction=(low+high)/2
                    for side in ('left','right'):state['joint_dofs'][f'{side}_thigh']['abduction_adduction']=adduction
                    errors=_check_preferred_joint_envelope(state,constraints)
                    if errors:raise RuntimeError(str(errors))
                    probe=copy.deepcopy(retarget);probe['poses'][pose]=retarget_pose_solution(solution,canonical,constraints,axis)
                    probe_contract=copy.deepcopy(static);probe_contract['root_translation_modes'][pose]='SOLVE_FULL_FOOT_CONTACT'
                    gate.realize_pose(pose,rig,canonical,constraints,probe,axis,probe_contract,runtime)
                    gap=heel_inner_gap()
                    if gap<desired_gap:low=adduction
                    else:high=adduction
                authority['closed_stance']={'hip_adduction_deg':adduction,'mesh_heel_inner_gap':gap,'target_gap':desired_gap,'method':'bounded source-mesh contact-aware hip adduction search; no independent foot yaw'}
            entry=retarget_pose_solution(solution,canonical,constraints,axis)
            custom=copy.deepcopy(retarget);custom['poses'][pose]=entry
            contract=copy.deepcopy(static);contract['root_translation_modes'][pose]='SOLVE_FULL_FOOT_CONTACT'
            realization=gate.realize_pose(pose,rig,canonical,constraints,custom,axis,contract,runtime)
            # Same accepted upper-body carriage in every baseline/candidate lower fixture.
            for name in ('Chest','Clavicle_L','Clavicle_R','Upper_Arm_L','Upper_Arm_R','Lower_Arm_L','Lower_Arm_R','Hand_L','Hand_R','Head'):
                q=upper[name]
                gate.static_core.apply_absolute_rig_rotation_via_matrix_basis(rig,name,Quaternion(q).to_matrix())
            gate.static_core.apply_ballet_hand_shape(rig,canonical,static)
            wrist=gate.validate_hand_axial_continuity(rig,canonical,constraints,visual)
            diagnostics={}
            for side in ('left','right'):
                shin=canonical['canonical_bones'][f'{side}_shin'];toe=canonical['canonical_bones'][f'{side}_toes']
                shin_basis=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[shin['rig_bone']],shin)
                # Canonical shin Z is anterior by declared rest contract; toe ray is observed posed longitudinal axis.
                heading=shin_basis.col[2]
                ray=rig.pose.bones[toe['rig_bone']].tail-rig.pose.bones[toe['rig_bone']].head
                pelvis=canonical['canonical_bones']['pelvis'];chest=canonical['canonical_bones']['chest']
                pelvis_basis=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[pelvis['rig_bone']],pelvis)
                chest_basis=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[chest['rig_bone']],chest)
                pelvis_yaw=math.degrees(math.atan2(pelvis_basis.col[2].dot(left),pelvis_basis.col[2].dot(front)))
                trunk_tilt=math.degrees(math.acos(max(-1,min(1,chest_basis.col[1].dot(up)))))
                diagnostics[side]=alignment_diagnostics(constraints,list(heading),list(ray),list(front),list(up),pelvis_yaw,trunk_tilt)
                if variant=='candidate' and diagnostics[side]['status']!='PASS':failures.append({'pose':pose,'side':side,'gate':'observed_knee_toe_tracking',**diagnostics[side]})
            rear={side:gate.static_core.evaluated_sample_points(rig,runtime['anchors'][side]['rear']) for side in ('left','right')}
            centers={side:sum(points,Vector())/len(points) for side,points in rear.items()}
            heel_span=(centers['left']-centers['right']).dot(left)
            if variant=='candidate' and pose in ('first','plie') and not -runtime['contact_tolerance']<=heel_inner_gap()<=runtime['metrics']['foot_chain_length']*.05:
                failures.append({'pose':pose,'gate':'closed_heel_stance','heel_inner_gap':heel_inner_gap()})
            results[f'{variant}/{pose}']={'authority':authority,'alignment':diagnostics,'realization':realization,'wrist':wrist,'observed_rear_mesh_center_span':heel_span,'heel_inner_gap':heel_inner_gap(),'canonical_validation':solution['validation']}
            for col,view in enumerate(('FRONT','THREE_QUARTER','SIDE')):
                gate.set_view(camera,center,rig,canonical,view,scale);gate.render_cell(scene,cells,row,col,pose,view,420)
    report={'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'source_glb_sha256':canonical['source']['sha256'],'fixtures':results,'failures':failures,'machine_status':'FAIL' if failures else 'PASS','ai_visual_status':'NOT_REVIEWED','camera_scale':camera.data.ortho_scale,'first_pose_scope':'Existing upper grammar + lower preferred envelopes/contact + measured heel inner-gap and observed tracking gates; no independent foot yaw','source_sha256':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve(),REPO/'tools/ballet_motion/distributed_turnout_v1.py',REPO/'build/visual_validation/BBM-1/elbow-path/report.json',REPO/'assets/ballet_motion/anatomical_constraints_v1.json',REPO/'assets/ballet_motion/retarget_axis_contract_v1.json')}}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['machine_status'],len(failures),'observed alignment failures')
    if failures:raise RuntimeError('Measured alignment gate failed; do not advance')

if __name__=='__main__':main()
