"""Source-bound foot semantic proof using existing contact/retarget authorities."""
import copy,json,sys,math,hashlib,subprocess
from pathlib import Path
import bpy
from mathutils import Vector,Quaternion,Matrix
REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'tools/blender'),str(REPO/'tools/ballet_motion')]
import render_foundation_pose_visual_gate_v1 as gate
from foot_semantics_v1 import foot_state,anatomical_plantar_from_canonical
from distributed_turnout_v1 import derive_turnout,alignment_diagnostics
from calibrated_rig_retarget import retarget_pose_solution
from canonical_pose_solver import _check_preferred_joint_envelope
from ballet_pose_validators import validate_pose


def apply_calibrated_basis(rig,name,basis):
    """Solve the imported affine rest relation with inverses, not transposes.

    Small imported rest-frame skew must not accumulate into a failed toe
    reconstruction. Joint translations remain the existing matrix-basis values.
    """
    bone=rig.pose.bones[name]
    rest=rig.data.bones[name].matrix_local.to_3x3()
    if bone.parent is None:
        delta=rest.inverted()@basis
    else:
        parent_rest=rig.data.bones[bone.parent.name].matrix_local.to_3x3()
        parent_pose=bone.parent.matrix.to_3x3()
        local_rest=parent_rest.inverted()@rest
        delta=local_rest.inverted()@parent_pose.inverted()@basis
    # Keep a true local rotation; independently verify the realized world
    # rotation and shaft length below/at the caller with unchanged tolerances.
    delta=delta.to_quaternion().normalized().to_matrix()
    matrix=delta.to_4x4();matrix.translation=bone.matrix_basis.translation.copy()
    bone.matrix_basis=matrix;bpy.context.view_layer.update()
    orthogonality=gate.matrix_max_error(delta.transposed()@delta,Matrix.Identity(3))
    if orthogonality>1e-5 or not .9999<=delta.determinant()<=1.0001:
        raise RuntimeError(f'{name}: local rotation contract failed: orthogonality={orthogonality}, determinant={delta.determinant()}')
    length_error=abs((bone.tail-bone.head).length-bone.bone.length)
    if length_error>bone.bone.length*1e-5:
        raise RuntimeError(f'{name}: unchanged bone length gate failed {length_error}')


def main():
    out=REPO/'build/visual_validation/BBM-3';out.mkdir(parents=True,exist_ok=True)
    (out/'report.json').unlink(missing_ok=True)
    for variant in ('baseline','candidate'):
        for image in (out/variant).glob('*.png'):image.unlink()
    load=lambda p:json.loads(p.read_text());base=REPO/'build/phase10_6';asset=REPO/'assets/ballet_motion'
    canonical=load(base/'low_poly_girl_canonical_ballet_profile_v1.json');constraints=load(base/'low_poly_girl_anatomical_constraint_profile_v1.json');poses=load(base/'low_poly_girl_canonical_pose_solver_v1.json');retarget=load(base/'low_poly_girl_calibrated_rig_retarget_v1.json');axis=load(asset/'retarget_axis_contract_v1.json');static=load(asset/'static_rig_application_contract_v1.json');visual=load(asset/'foundation_pose_visual_gate_v1.json');grammar=load(base/'low_poly_girl_ballet_pose_grammar_profile_v1.json')
    prior=load(REPO/'build/visual_validation/BBM-2/report.json')
    if prior['ai_visual_status']!='AI_VISUAL_PASS':raise RuntimeError('BBM-2 must pass')
    source=REPO/canonical['source']['path']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=canonical['source']['sha256']:raise RuntimeError('Source GLB changed')
    bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source));rig=gate.static_core.find_armature(canonical['source']['armature'])
    for obj in bpy.context.scene.objects:
        if obj.animation_data:obj.animation_data_clear()
    runtime=gate.prepare_contact_runtime(rig,canonical,static);frame=canonical['body_frame']['declared_axes_armature_local'];up=Vector(frame['up']);front=Vector(frame['front']);left=Vector(frame['left'])
    scene=bpy.context.scene;gate.configure_workbench(scene,420);camera,center,scale=gate.create_camera(rig,canonical)
    upper=load(REPO/'build/visual_validation/BBM-1/elbow-path/report.json')['samples'][0]['orientations_wxyz']
    adduction=prior['fixtures']['candidate/first']['authority']['closed_stance']['hip_adduction_deg']
    neutral_report=load(REPO/'build/visual_validation/BBM-0/baseline/geometry_report.json')
    neutral={side:neutral_report['poses']['bras_bas']['realization']['full_foot_orientation'][side]['plantar_dorsiflexion_deg'] for side in ('left','right')}
    records={};failures=[]
    def upper_carriage():
        for name in ('Chest','Clavicle_L','Clavicle_R','Upper_Arm_L','Upper_Arm_R','Lower_Arm_L','Lower_Arm_R','Hand_L','Hand_R','Head'):
            gate.static_core.apply_absolute_rig_rotation_via_matrix_basis(rig,name,Quaternion(upper[name]).to_matrix())
        gate.static_core.apply_ballet_hand_shape(rig,canonical,static)
    def support_front_offset():
        points=[]
        for side in ('left','right'):
            fore=gate.static_core.evaluated_sample_points(rig,runtime['anchors'][side]['fore'])
            points+=sorted(fore,key=lambda p:p.dot(up))[:max(3,len(fore)//5)]
        pelvis=rig.pose.bones[canonical['canonical_bones']['pelvis']['rig_bone']].head
        return (sum(points,Vector())/len(points)-pelvis).dot(front),points
    for variant in ('baseline','candidate'):
        cells=out/variant;cells.mkdir(exist_ok=True)
        for row,label in enumerate(('flat','demi_pointe','pointe_ready')):
            solution=copy.deepcopy(poses['solutions']['bras_bas']);state=solution['state'];lower=poses['solutions']['fifth']['state']
            state['joint_dofs'].update(copy.deepcopy(lower['joint_dofs']));state['turnout']=copy.deepcopy(lower['turnout']);state['contacts']={side:'FULL_FOOT' if label=='flat' else 'FOREFOOT' for side in ('left','right')}
            target=foot_state(constraints,{'flat':'FLAT','demi_pointe':'DEMI_POINTE','pointe_ready':'POINTE_READY'}[label],{'flat':0,'demi_pointe':35,'pointe_ready':50}[label],35 if label=='demi_pointe' else 0)
            pose='releve' if label=='demi_pointe' else label;state['pose']=pose;solution['pose']=pose
            if label=='demi_pointe':state['scalars']={'left_heel_height':.05,'right_heel_height':.05}
            for side in ('left','right'):
                state['joint_dofs'][f'{side}_thigh'].update({'abduction_adduction':0 if label=='pointe_ready' and variant=='candidate' else adduction,'flexion_extension':0,'internal_external_rotation':45})
                state['joint_dofs'][f'{side}_shin']['flexion_extension']=0
                state['joint_dofs'][f'{side}_foot'].update({'plantar_dorsiflexion':target['ankle_plantar_dorsiflexion_deg'],'inversion_eversion':0})
                state['joint_dofs'][f'{side}_toes']['toe_flexion_extension']=target['mtp_toe_flexion_extension_deg']
                derived=derive_turnout(constraints,45,0)
                state['turnout'][side].update({'hip_external_rotation_deg':45,'knee_flexion_deg':0,'knee_external_rotation_deg':derived['knee_external_rotation_deg'],'independent_foot_yaw_deg':0})
            realized_angles={}
            def realize():
                violations=_check_preferred_joint_envelope(state,constraints)
                if violations:raise RuntimeError(str(violations))
                solution['validation']=validate_pose(state,grammar['poses']['bras_bas'],constraints,canonical)
                custom=copy.deepcopy(retarget);custom['poses'][pose]=retarget_pose_solution(solution,canonical,constraints,axis)
                contract=copy.deepcopy(static);contract['root_translation_modes'][pose]='SOLVE_FULL_FOOT_CONTACT' if label=='flat' else 'SOLVE_FOREFOOT_CONTACT'
                if variant=='baseline' or label=='flat':
                    result=gate.realize_pose(pose,rig,canonical,constraints,custom,axis,contract,runtime)
                else:
                    entry=custom['poses'][pose]
                    gate.static_core.apply_rotation_deltas(rig,entry)
                    # Serialized rotations have bounded rounding error. Project
                    # each local rotation to SO(3) before errors can accumulate.
                    for bone in rig.pose.bones:
                        matrix=bone.matrix_basis.copy()
                        rotation=matrix.to_quaternion().normalized().to_matrix().to_4x4()
                        rotation.translation=matrix.translation
                        bone.matrix_basis=rotation
                    bpy.context.view_layer.update()
                    for side in ('left','right'):
                        foot=canonical['canonical_bones'][f'{side}_foot'];toe=canonical['canonical_bones'][f'{side}_toes']
                        parent,rest=gate.static_core.canonical_parent_and_rest_local(rig,canonical,f'{side}_foot')
                        raw=neutral[side]+target['ankle_plantar_dorsiflexion_deg']
                        desired=(parent@rest@Matrix.Rotation(math.radians(-raw),3,'X')).to_quaternion().normalized().to_matrix()
                        apply_calibrated_basis(rig,foot['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(foot,desired))
                        toe_parent,toe_rest=gate.static_core.canonical_parent_and_rest_local(rig,canonical,f'{side}_toes')
                        toe_desired=(toe_parent@toe_rest@Matrix.Rotation(math.radians(target['mtp_toe_flexion_extension_deg']),3,'X')).to_quaternion().normalized().to_matrix()
                        apply_calibrated_basis(rig,toe['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(toe,toe_desired))
                        toe_observed=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[toe['rig_bone']],toe)
                        toe_delta=(toe_parent@toe_rest).transposed()@toe_observed
                        measured_toe=round(gate.static_core.extract_exact_toe_flexion(toe_delta),3)
                        foot_state(constraints,target['state'],target['ankle_plantar_dorsiflexion_deg'],measured_toe)
                        toe_error=gate.matrix_max_error(toe_observed,toe_desired)
                        if toe_error>axis['thresholds']['hierarchy_reconstruction_max_error']:
                            raise RuntimeError(f'Toe matrix reconstruction gate failed {side}: {toe_error}; desired={list(toe_desired)}; observed={list(toe_observed)}')
                        observed=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[foot['rig_bone']],foot)
                        delta=(parent@rest).transposed()@observed
                        measured=gate.static_core.extract_exact_ankle_plantar(delta)
                        decoded=anatomical_plantar_from_canonical(constraints,round(measured,3),neutral[side])
                        roundtrip=gate.matrix_max_error(observed,desired)
                        if decoded['status']!='PASS' or roundtrip>axis['thresholds']['hierarchy_reconstruction_max_error']:
                            raise RuntimeError(f'Calibrated ankle gate failed {side}: {decoded}, matrix error {roundtrip}')
                        realized_angles[side]={**decoded,'matrix_roundtrip_error':roundtrip,'measured_toe_flexion_deg':measured_toe,'toe_matrix_roundtrip_error':toe_error,'independent_foot_yaw_deg':0}
                    before=gate.static_core.contact_heights(rig,runtime['anchors'],up,float(runtime['sampling']['low_height_quantile']))
                    shift=gate.static_core.root_shift_for_contact('SOLVE_FOREFOOT_CONTACT',runtime['rest_heights'],before)
                    gate.static_core.set_root_translation_armature_space(rig,canonical['canonical_bones']['pelvis']['rig_bone'],up*shift)
                    after=gate.static_core.contact_heights(rig,runtime['anchors'],up,float(runtime['sampling']['low_height_quantile']))
                    contact=gate.static_core.contact_errors('SOLVE_FOREFOOT_CONTACT',runtime['rest_heights'],after)
                    if contact['max_abs_error']>runtime['contact_tolerance']:raise RuntimeError('Unchanged deformed forefoot contact gate failed')
                    heel={side:after[side]['rear']-runtime['rest_heights'][side]['rear'] for side in ('left','right')}
                    if min(heel.values())<=runtime['metrics']['foot_chain_length']*.05:raise RuntimeError('Heel did not rise')
                    result={'contact':contact,'root_up_shift':shift,'heel_lifts':heel,'calibrated_anatomical_angles':copy.deepcopy(realized_angles)}
                upper_carriage();return result
            realization=realize();balance_intent={}
            if variant=='candidate' and label!='flat':
                lo,hi=-12.,0.
                for iteration in range(10):
                    hip=(lo+hi)/2
                    for side in ('left','right'):state['joint_dofs'][f'{side}_thigh']['flexion_extension']=hip
                    realization=realize();offset,points=support_front_offset()
                    if offset<0:lo=hip
                    else:hi=hip
                balance_intent={'hip_flexion_extension_deg':hip,'pelvis_to_low_forefoot_centroid_front_offset':offset,'scope':'pelvis support proxy only; whole-body COM belongs to BBM-4'}
            wrist=gate.validate_hand_axial_continuity(rig,canonical,constraints,visual)
            offset,support=support_front_offset();alignment={}
            for side in ('left','right'):
                shin=canonical['canonical_bones'][f'{side}_shin'];toe=canonical['canonical_bones'][f'{side}_toes'];heading=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[shin['rig_bone']],shin).col[2];ray=rig.pose.bones[toe['rig_bone']].tail-rig.pose.bones[toe['rig_bone']].head
                alignment[side]=alignment_diagnostics(constraints,list(heading),list(ray),list(front),list(up))
                if variant=='candidate' and alignment[side]['status']!='PASS':failures.append({'pose':label,'side':side,'gate':'observed_alignment',**alignment[side]})
            if variant=='candidate' and label!='flat' and abs(offset)>runtime['metrics']['foot_chain_length']*.1:failures.append({'pose':label,'gate':'pelvis_forefoot_proxy','offset':offset})
            records[f'{variant}/{label}']={'semantic_intent':target,'realization':realization,'alignment':alignment,'wrist':wrist,'balance_intent':balance_intent,'stance_scope':'open symmetric preparation for pointe-ready; closed first for flat/demi' if variant=='candidate' else 'previous closed first foot organization','pelvis_support_front_offset':offset,'low_forefoot_support_points':[list(p) for p in support],'canonical_state':copy.deepcopy(state)}
            for col,view in enumerate(('FRONT','THREE_QUARTER','SIDE')):
                gate.set_view(camera,center,rig,canonical,view,scale);gate.render_cell(scene,cells,row,col,label,view,420)
    report={'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'source_glb_sha256':canonical['source']['sha256'],'ankle_neutral_offset_deg':neutral,'ankle_reference':'source-bound flat-contact neutral; unchanged anatomical envelopes evaluated relative to neutral','fixtures':records,'failures':failures,'machine_status':'FAIL' if failures else 'PASS','ai_visual_status':'NOT_REVIEWED','camera_scale':camera.data.ortho_scale,'source_sha256':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve(),REPO/'tools/ballet_motion/foot_semantics_v1.py',REPO/'build/visual_validation/BBM-2/report.json',REPO/'build/visual_validation/BBM-0/baseline/geometry_report.json',REPO/'assets/ballet_motion/anatomical_constraints_v1.json')}}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if failures:raise RuntimeError(str(failures))
    print('BBM-3 MACHINE_PASS; actual visual review required')

if __name__=='__main__':
    try:main()
    except Exception as exc:
        out=REPO/'build/visual_validation/BBM-3';out.mkdir(parents=True,exist_ok=True)
        if not (out/'report.json').exists():
            (out/'report.json').write_text(json.dumps({'machine_status':'FAIL','ai_visual_status':'NOT_REVIEWED','fatal_error':str(exc),'source_sha256':{str(Path(__file__).resolve().relative_to(REPO)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}},indent=2)+'\n')
        raise
