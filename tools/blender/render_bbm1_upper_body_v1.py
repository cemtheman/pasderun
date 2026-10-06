"""Accepted arm v0.6 replay under the locked BBM camera and geometry gates."""
import argparse
import copy
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path
import bpy
from mathutils import Matrix, Vector

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO/'tools/motion_studio'))
sys.path.insert(0, str(REPO/'tools/blender/motion_studio'))
sys.path.insert(0, str(REPO/'tools/blender'))
from bbm_upper_body_v1 import coordinate_samples
from palm_roll_path_v1 import select_roll_path
from accepted_arm_visual import joint_targets
from accepted_arm_visual_v0_6 import align_hand_tips, measured_hand_mesh_projection
from static_pose_preview_v0_3 import apply_solution
from hand_clearance_candidate import shifted_solution
from first_position_candidate import guide_first_position
from second_elbow_line import solve_second_forward_line
from port_de_bras_path import sample_port_de_bras
import render_foundation_pose_visual_gate_v1 as gate
sys.path.insert(0, str(REPO/'tools/ballet_motion'))
from calibrated_rig_retarget import _wrist_2dof_target_basis
from rig_retarget_math import basis_from_length_and_front, local_twist_y


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--hand-shape',action='store_true')
    parser.add_argument('--phrase-coordination',action='store_true')
    parser.add_argument('--preview',action='store_true')
    parser.add_argument('--hand-line',action='store_true')
    parser.add_argument('--palm-intent',action='store_true')
    parser.add_argument('--palm-opening-lead',type=float,default=1.0)
    parser.add_argument('--global-roll',action='store_true')
    parser.add_argument('--neutral-wrist-intent',action='store_true')
    parser.add_argument('--elbow-path',action='store_true')
    parser.add_argument('--forearm-gauge',choices=('elbow-plane','rig-rest'),default='elbow-plane')
    parser.add_argument('--diagnostic-render',action='store_true',help='Historical failed replay only; retains MACHINE_FAIL and is never acceptable evidence')
    parser.add_argument('--wrist-mode', choices=('historical','two-dof','coordinated'), default='historical')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:])
    out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    load=lambda p:json.loads(p.read_text())
    source_hashes={str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve(),REPO/'tools/motion_studio/bbm_upper_body_v1.py',REPO/'tools/motion_studio/palm_roll_path_v1.py',REPO/'assets/ballet_motion/retarget_axis_contract_v1.json',REPO/'assets/ballet_motion/static_rig_application_contract_v1.json',REPO/'build/phase10_6/low_poly_girl_anatomical_constraint_profile_v1.json')}
    calibration=load(REPO/'build/visual_validation/BBM-1/calibration.json')
    reference=load(REPO/'build/visual_validation/BBM-1/accepted_reference.json')
    canonical=load(REPO/'build/phase10_6/low_poly_girl_canonical_ballet_profile_v1.json')
    constraints=load(REPO/'build/phase10_6/low_poly_girl_anatomical_constraint_profile_v1.json')
    visual=load(REPO/'assets/ballet_motion/foundation_pose_visual_gate_v1.json')
    provenance=load(REPO/'tools/visual_validation/accepted_arm_provenance.json')
    params=provenance['historic_inputs'];frame=calibration['anatomical_frame']
    start=shifted_solution(joint_targets(reference,calibration,'bras_bas'),frame,params['bras_bas_outward_wrist_shift'])
    high=shifted_solution(joint_targets(reference,calibration,'en_avant'),frame,params['en_avant_outward_wrist_shift'],'body_outward')
    height=Vector(calibration['canonical_bones']['spine_mid']['head_local']).dot(Vector(frame['up']))
    middle=guide_first_position(start,high,frame,navel_region_height=height)
    end,diagnostics=solve_second_forward_line(joint_targets(reference,calibration,'second'),frame)
    samples=sample_port_de_bras({'bras_bas':start,'first_position':middle,'second':end},frame,order=('bras_bas','first_position','second'),guide_clearance=params['guide_clearance'],guide_opening_lead=params['guide_opening_lead'],opening_arc_up_fraction=params['opening_arc_up_fraction'],opening_arc_front_fraction=params['opening_arc_front_fraction'])
    if args.phrase_coordination:samples=coordinate_samples(samples,frame,preserve_elbow_path=args.elbow_path)
    source=REPO/canonical['source']['path']
    source_sha=hashlib.sha256(source.read_bytes()).hexdigest()
    if source_sha!=provenance['source_glb_sha256']:raise RuntimeError('Locked GLB digest mismatch')
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(source))
    rig=gate.static_core.find_armature(canonical['source']['armature'])
    for obj in bpy.context.scene.objects:
        if obj.animation_data:obj.animation_data_clear()
    scene=bpy.context.scene
    engine=gate.configure_workbench(scene,420)
    camera,center,scale=gate.create_camera(rig,canonical)
    rows=[];records=[];errors=[];previous_orientations={};max_step=0;twist_by_frame=[];forearm_reference_bases={}
    palm_local={};palm_anchors={}
    if args.palm_intent:
        for side in ('left','right'):
            name=canonical['canonical_bones'][f'{side}_hand']['rig_bone']
            chains={digit:gate.static_core._finger_chain_from_hand_hierarchy(rig,name,digit) for digit in ('index','middle','pinky')}
            normal=gate.static_core._ballet_hand_palm_frame(rig,name,chains)[2]
            palm_local[side]=rig.pose.bones[name].matrix.to_3x3().normalized().transposed()@normal
            palm_anchors[side]=[]
        for anchor in (0,24,48):
            for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
            bpy.context.view_layer.update()
            apply_solution(rig,samples[anchor]);align_hand_tips(rig,samples[anchor])
            for side in ('left','right'):
                name=canonical['canonical_bones'][f'{side}_hand']['rig_bone']
                palm_anchors[side].append(rig.pose.bones[name].matrix.to_3x3().normalized()@palm_local[side])
        for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
        bpy.context.view_layer.update()
    rest_anchors={name:rig.pose.bones[name].head.copy() for name in ('Hips','Foot_L','Foot_R','Toes_L','Toes_R')}
    roll_candidates={'left':[],'right':[]};roll_plan={}
    for planning in ([True,False] if args.global_roll else [False]):
        rows=[];records=[];errors=[];previous_orientations={};max_step=0;twist_by_frame=[]
        for index,sample in enumerate(samples):
            for bone in rig.pose.bones:bone.matrix_basis=Matrix.Identity(4)
            bpy.context.view_layer.update()
            sample=copy.deepcopy(sample)
            if args.hand_line:
                t=(index if index<=24 else index-24)/24
                weight=math.sin(math.pi*t)**2 if index>24 else 0.0
                for side,arm in sample['arms'].items():
                    old_direction=(Vector(arm['hand'])-Vector(arm['wrist'])).normalized()
                    fore_direction=(Vector(arm['wrist'])-Vector(arm['elbow'])).normalized()
                    direction=old_direction.lerp(fore_direction,weight).normalized()
                    hand_length=(Vector(arm['hand'])-Vector(arm['wrist'])).length
                    arm['hand']=list(Vector(arm['wrist'])+direction*hand_length)
            if args.phrase_coordination:
                c=sample['coordination']
                if index>24:
                    t=c['head_phase'];angle=.25*(t*t*(3-2*t))
                    chest=rig.pose.bones[calibration['canonical_bones']['chest']['rig_bone']]
                    gate.static_core.apply_absolute_rig_rotation_via_matrix_basis(rig,chest.name,Matrix.Rotation(math.radians(angle),3,Vector(frame['up']))@chest.matrix.to_3x3().normalized())
                for side,arm in sample['arms'].items():
                    name=calibration['canonical_bones'][f'{side}_clavicle']['rig_bone']
                    bone=rig.pose.bones[name]
                    angle=math.radians(c['clavicle_carriage_deg'])*(1 if side=='left' else -1)
                    gate.static_core.apply_absolute_rig_rotation_via_matrix_basis(rig,name,Matrix.Rotation(angle,3,Vector(frame['front']))@bone.matrix.to_3x3().normalized())
                    bpy.context.view_layer.update()
                    shift=rig.pose.bones[arm['bone_names'][0]].head-Vector(arm['shoulder'])
                    for joint in ('shoulder','elbow','wrist','hand'):arm[joint]=list(Vector(arm[joint])+shift)
                if index>24:
                    t=c['head_phase'];yaw=4*(t*t*(3-2*t))
                    head=rig.pose.bones[calibration['canonical_bones']['head']['rig_bone']]
                    gate.static_core.apply_absolute_rig_rotation_via_matrix_basis(rig,head.name,Matrix.Rotation(math.radians(yaw),3,Vector(frame['up']))@head.matrix.to_3x3().normalized())
            residuals=apply_solution(rig,sample)
            hand_residuals=align_hand_tips(rig,sample)
            if args.wrist_mode=='coordinated':
                axis_contract=load(REPO/'assets/ballet_motion/retarget_axis_contract_v1.json')
                for side,arm in sample['arms'].items():
                    names=canonical['canonical_bones']
                    fore=names[f'{side}_forearm'];hand=names[f'{side}_hand']
                    direction=(Vector(arm['wrist'])-Vector(arm['elbow'])).normalized()
                    upper_direction=(Vector(arm['elbow'])-Vector(arm['shoulder'])).normalized()
                    hinge=upper_direction.cross(direction)
                    if hinge.length<1e-7:raise RuntimeError('Elbow bend plane singular; do not invent a twist gauge')
                    hinge.normalize()
                    front_axis=hinge.cross(direction).normalized()
                    base_matrix=gate.static_core.basis_from_columns(hinge,direction,front_axis)
                    if args.forearm_gauge=='rig-rest':
                        base_matrix=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[fore['rig_bone']],fore)
                    forearm_reference_bases[side]=base_matrix
                    fore_base=[list(row) for row in base_matrix]
                    hand_direction=list((Vector(arm['hand'])-Vector(arm['wrist'])).normalized())
                    old_hand=rig.pose.bones[arm['bone_names'][2]].matrix.to_3x3().normalized()
                    desired_palm=None
                    if args.palm_intent:
                        leg=0 if index<=24 else 1
                        t=(index-leg*24)/24
                        if leg==1:t=min(1.0,t*args.palm_opening_lead)
                        eased=t*t*(3-2*t)
                        desired_palm=palm_anchors[side][leg].lerp(palm_anchors[side][leg+1],eased)
                        desired_palm-=Vector(hand_direction)*desired_palm.dot(Vector(hand_direction))
                        if desired_palm.length<1e-7:raise RuntimeError('Palm intent projection singular')
                        desired_palm.normalize()
                    feasible=[]
                    for twist in range(-80,86):
                        basis=local_twist_y(fore_base,twist)
                        fit_direction=Vector(hand_direction)
                        if args.neutral_wrist_intent and index>24:
                            neutral=Matrix(basis)@Matrix(fore['canonical_rest_contract']['basis_armature_local']).transposed()@Matrix(hand['canonical_rest_contract']['basis_armature_local'])
                            neutral_rig=gate.static_core.rig_basis_from_canonical_pose(hand,neutral)
                            weight=math.sin(math.pi*(index-24)/24)**2
                            fit_direction=fit_direction.lerp(neutral_rig.col[1],weight).normalized()
                        hand_basis,evidence=_wrist_2dof_target_basis(list(fit_direction),basis,fore['canonical_rest_contract']['basis_armature_local'],hand['canonical_rest_contract']['basis_armature_local'],constraints,axis_contract)
                        new_rig=gate.static_core.rig_basis_from_canonical_pose(hand,Matrix(hand_basis))
                        error=(new_rig.col[1]-fit_direction).length*hand['length']
                        if error<=arm['arm_reach']*.005*.9999:
                            orientation=2*math.acos(min(1.0,abs(old_hand.to_quaternion().normalized().dot(new_rig.to_quaternion().normalized()))))
                            if desired_palm is not None:
                                actual_palm=(new_rig@palm_local[side]).normalized()
                                orientation=math.acos(max(-1.0,min(1.0,desired_palm.dot(actual_palm))))
                            previous_hand=previous_orientations.get(hand['rig_bone'])
                            if previous_hand is not None and not args.global_roll:
                                delta=math.degrees(previous_hand.rotation_difference(new_rig.to_quaternion()).angle)
                                delta=min(delta,360-delta)
                                if delta>20:continue
                            feasible.append((orientation,abs(twist),twist,basis,hand_basis,evidence,list(fit_direction)))
                    if not feasible:
                        errors.append({'frame':index+1,'gate':'preferred_forearm_wrist_fit','side':side,'reason':'No feasible fit inside unchanged preferred envelopes and continuity bound'})
                        continue
                    if planning:
                        roll_candidates[side].append(feasible)
                    best=min(feasible,key=lambda x:(x[0],x[1]))
                    if args.global_roll and not planning:
                        best=next(node for node in feasible if node[2]==roll_plan[side][index])
                    if args.neutral_wrist_intent:
                        hand_length=(Vector(arm['hand'])-Vector(arm['wrist'])).length
                        arm['hand']=list(Vector(arm['wrist'])+Vector(best[6])*hand_length)
                    twist_by_frame.append({'frame':index+1,'side':side,'pronation_supination_deg':best[2],'wrist_dofs':best[5],'palm_error_deg':math.degrees(best[0]) if desired_palm is not None else None,'target_palm_normal':list(desired_palm) if desired_palm is not None else None,'achieved_palm_normal':list((gate.static_core.rig_basis_from_canonical_pose(hand,Matrix(best[4]))@palm_local[side]).normalized()) if desired_palm is not None else None})
                    gate.static_core.apply_absolute_rig_rotation_via_matrix_basis(rig,fore['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(fore,Matrix(best[3])))
                    gate.static_core.apply_absolute_rig_rotation_via_matrix_basis(rig,hand['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(hand,Matrix(best[4])))
                    actual=(rig.pose.bones[arm['bone_names'][2]].tail-Vector(arm['hand'])).length
                    hand_residuals[side]=actual
                    if actual>arm['arm_reach']*.005:errors.append({'frame':index+1,'gate':'accepted_hand_endpoint','side':side,'value':actual,'tolerance':arm['arm_reach']*.005})
            if args.wrist_mode=='two-dof':
                for side,arm in sample['arms'].items():
                    parent,rest_local=gate.static_core.canonical_parent_and_rest_local(rig,canonical,f'{side}_hand')
                    base=parent@rest_local
                    target=(Vector(arm['hand'])-Vector(arm['wrist'])).normalized()
                    direction=base.transposed()@target
                    flexion=math.degrees(math.atan2(direction.z,direction.y))
                    limits=constraints['joint_limits']['wrist_2dof']['dofs']
                    f=limits['flexion_extension']['preferred']
                    flexion=max(f['min'],min(f['max'],flexion))
                    projected=direction.y*math.cos(math.radians(flexion))+direction.z*math.sin(math.radians(flexion))
                    deviation=math.degrees(math.atan2(-direction.x,projected))
                    d=limits['radial_ulnar_deviation']['preferred']
                    deviation=max(d['min'],min(d['max'],deviation))
                    gate.static_core.apply_hand_wrist_candidate(rig,canonical,side,flexion,deviation)
                    actual=(rig.pose.bones[arm['bone_names'][2]].tail-Vector(arm['hand'])).length
                    hand_residuals[side]=actual
                    if actual>arm['arm_reach']*.005:errors.append({'frame':index+1,'gate':'accepted_hand_endpoint','side':side,'value':actual,'tolerance':arm['arm_reach']*.005})
            if args.hand_shape:
                static_contract=load(REPO/'assets/ballet_motion/static_rig_application_contract_v1.json')
                gate.static_core.apply_ballet_hand_shape(rig,canonical,static_contract)
            projection=measured_hand_mesh_projection(rig,calibration)
            if projection['projected_gap_armature_units']<0:errors.append({'frame':index+1,'gate':'hand_mesh_gap','value':projection['projected_gap_armature_units']})
            try:
                wrist=gate.validate_hand_axial_continuity(rig,canonical,constraints,visual)
            except RuntimeError as exc:
                wrist={'status':'FAIL','reason':str(exc)};errors.append({'frame':index+1,'gate':'wrist_continuity','reason':str(exc)})
            orientations={}
            for name in ('Upper_Arm_L','Upper_Arm_R','Lower_Arm_L','Lower_Arm_R','Hand_L','Hand_R','Clavicle_L','Clavicle_R','Head','Chest'):
                q=rig.pose.bones[name].matrix.to_quaternion().normalized()
                if name in previous_orientations:
                    step=math.degrees(previous_orientations[name].rotation_difference(q).angle)
                    step=min(step,360-step);max_step=max(max_step,step)
                    if step>30:errors.append({'frame':index+1,'gate':'joint_phase_continuity','bone':name,'step_deg':step,'max_step_deg':30})
                previous_orientations[name]=q
                orientations[name]=list(q)
            for name,rest in rest_anchors.items():
                drift=(rig.pose.bones[name].head-rest).length
                if drift>1e-6:errors.append({'frame':index+1,'gate':'root_contact_drift','bone':name,'value':drift})
            for side,arm in sample['arms'].items():
                u=(Vector(arm['elbow'])-Vector(arm['shoulder'])).normalized();v=(Vector(arm['wrist'])-Vector(arm['elbow'])).normalized()
                flexion=math.degrees(math.acos(max(-1,min(1,u.dot(v)))))
                envelope=constraints['joint_limits']['elbow_twist']['dofs']['flexion_extension']['preferred']
                if not envelope['min']<=flexion<=envelope['max']:errors.append({'frame':index+1,'gate':'elbow_preferred_envelope','side':side,'value':flexion})
            records.append({'orientations_wxyz':orientations,'frame':index+1,'residuals':residuals,'hand_residuals':hand_residuals,'hand_gap':projection,'wrist':wrist})
            if args.preview and not errors and not planning:
                preview=out/'preview_frames';preview.mkdir(exist_ok=True)
                gate.set_view(camera,center,rig,canonical,'FRONT',scale)
                gate.render_cell(scene,preview,index,0,f'frame_{index+1:02d}','FRONT',420)
            # Never turn a failed geometric sample into approved visual evidence.
            if not planning and index in (0,12,24,36,48) and (not errors or (args.diagnostic_render and args.wrist_mode=='historical')):
                cells=[]
                for column,view in enumerate(('FRONT','THREE_QUARTER','SIDE')):
                    gate.set_view(camera,center,rig,canonical,view,scale)
                    cells.append(gate.render_cell(scene,out,len(rows),column,f'frame_{index+1:02d}',view,420))
                rows.append(cells)
        if planning:
            for side,layers in roll_candidates.items():
                hand=canonical['canonical_bones'][f'{side}_hand']
                candidates=[[{'palm_error_rad':node[0],'quaternion':tuple(gate.static_core.rig_basis_from_canonical_pose(hand,Matrix(node[4])).to_quaternion().normalized())} for node in layer] for layer in layers]
                chosen=select_roll_path(candidates)
                roll_plan[side]=[layer[index][2] for layer,index in zip(layers,chosen)]
    report={'input_sha256':source_hashes,'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'historical_reference':provenance,'source_glb_sha256':source_sha,'engine':engine,'blender_version':bpy.app.version_string,'orthographic_scale':camera.data.ortho_scale,'sample_frames':[1,13,25,37,49],'samples':records,'gate_failures':errors,'machine_status':'FAIL' if errors else 'PASS','ai_visual_status':'NOT_REVIEWED','second_diagnostics':diagnostics,'wrist_mode':args.wrist_mode,'hand_shape':args.hand_shape,'phrase_coordination':args.phrase_coordination,'hand_line':args.hand_line,'palm_intent':args.palm_intent,'global_roll':args.global_roll,'neutral_wrist_intent':args.neutral_wrist_intent,'elbow_path':args.elbow_path,'forearm_gauge':args.forearm_gauge,'palm_opening_lead':args.palm_opening_lead,'palm_anchor_normals':{side:[list(v) for v in values] for side,values in palm_anchors.items()},'diagnostic_only':args.diagnostic_render,'max_adjacent_joint_rotation_deg':max_step,'forearm_wrist_fit':twist_by_frame,'root_and_contact_anchors_unchanged':True if not any(x['gate']=='root_contact_drift' for x in errors) else False}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if len(rows)==5:gate.save_contact_sheet(rows,out/'frame_strip.png',420)
    if errors:raise RuntimeError(f'{len(errors)} unchanged hard geometry gate failures; inspect report.json')
    print('BBM-1 ACCEPTED REPLAY MACHINE_PASS; visual review pending')


if __name__=='__main__':main()
