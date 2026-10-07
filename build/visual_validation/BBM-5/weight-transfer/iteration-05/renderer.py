"""Planted bilateral contact with explicit quasistatic pelvis transfer."""
import copy,json,sys,math,hashlib,subprocess
from pathlib import Path
import numpy as np
from mathutils import Vector,Quaternion
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO/'tools/blender'),str(REPO/'tools/ballet_motion')]
from bbm_body_runtime_v1 import BodyRuntime,gate,surface_centroid
from render_bbm3_foot_v1 import apply_calibrated_basis
from distributed_turnout_v1 import derive_turnout,alignment_diagnostics
from weight_transfer_v1 import transfer_intent,weightbearing_roles
from support_balance_v1 import balance_diagnostics
from foot_semantics_v1 import foot_state,anatomical_plantar_from_canonical


def main():
    out=REPO/'build/visual_validation/BBM-5/weight-transfer';out.mkdir(parents=True,exist_ok=True);(out/'report.json').unlink(missing_ok=True)
    prior=json.loads((REPO/'build/visual_validation/BBM-5/report.json').read_text())
    if prior['machine_status']!='PASS' or prior['ai_visual_status']!='AI_VISUAL_PASS':raise RuntimeError('Plié proof required')
    body=BodyRuntime();base=copy.deepcopy(prior['samples']['candidate/12']['canonical_state']);approved=[prior['samples'][f'candidate/{i:02d}']['canonical_state'] for i in range(25)];records={};failures=[];reference=None;controls=[('left_thigh','abduction_adduction',-20,20),('left_thigh','flexion_extension',-12,32),('right_thigh','abduction_adduction',-20,20),('right_thigh','flexion_extension',-12,32),('right_shin','flexion_extension',0,32)]
    keys={0:0,6:1,12:2,18:3,24:4}
    def realize(state,offset,roles):
        for side in ('left','right'):
            knee=state['joint_dofs'][f'{side}_shin']['flexion_extension'];state['turnout'][side].update({'knee_flexion_deg':knee,'knee_external_rotation_deg':derive_turnout(body.constraints,45,knee)['knee_external_rotation_deg']})
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
        if variant=='candidate':
            fraction=offset/.08
            names=[body.canonical['canonical_bones'][n]['rig_bone'] for n in ('spine_lower','spine_mid')]+['Chest','Clavicle_L','Clavicle_R','Upper_Arm_L','Upper_Arm_R','Lower_Arm_L','Lower_Arm_R','Hand_L','Hand_R','Head']
            original={n:body.rig.pose.bones[n].matrix.to_quaternion().normalized().to_matrix() for n in names}
            for j,n in enumerate(names):
                share=(j+1)/3 if j<2 else 1
                rotation=Quaternion(body.left,math.radians(-5.5*fraction*share))@Quaternion(body.front,math.radians(-2.5*fraction*share))
                apply_calibrated_basis(body.rig,n,rotation.to_matrix()@original[n])
            chest=body.rig.pose.bones['Chest'];tilt=math.degrees((chest.tail-chest.head).angle(body.up))
            policy=next(c for c in body.grammar['poses']['plie']['checks'] if c.get('name')=='trunk_tilt_deg')
            if tilt>policy['max']:raise RuntimeError('Existing trunk tilt gate failed')
            trunk={'backward_transport_deg':5.5*fraction,'lateral_transport_deg':2.5*fraction,'observed_chest_tilt_deg':tilt,'existing_plie_limit_deg':policy['max'],'spine_distribution':[1/3,2/3,1],'upper_carriage_transport':'shared world rotation preserves local arm/head relationship'}
        heights=gate.static_core.contact_heights(body.rig,body.runtime['anchors'],body.up,body.q);errors={s:{r:heights[s][r]-body.runtime['rest_heights'][s][r] for r in ('rear','fore')} for s in ('left','right')};maximum=max(abs(e) for v in errors.values() for e in v.values())
        centers={s:sum(gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][s]['rear']),Vector())/len(body.runtime['anchors'][s]['rear']) for s in ('left','right')}
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
        return {'trunk_transport':trunk,'balance':balance,'contact_errors':errors,'contact_max_abs':maximum,'rear_centers':{s:list(c) for s,c in centers.items()},'root_intent_left':offset,'root_intent_error':root_error,'alignment':alignment,'right_foot_proof':{'anatomical':decoded,'matrix_error':error},'canonical_state':copy.deepcopy(state),'wrist':gate.validate_hand_axial_continuity(body.rig,body.canonical,body.constraints,body.visual)}
    for variant in ('baseline','candidate'):
        cells=out/variant;cells.mkdir(exist_ok=True);preview=cells/'preview';preview.mkdir(exist_ok=True)
        for p in cells.rglob('*.png'):p.unlink()
        previous=None
        for i in range(25):
            t=i/24;intent=transfer_intent(t);state=copy.deepcopy(base);state['joint_dofs']['left_shin']['flexion_extension']=intent['left_knee_flexion_deg'];
            knee=intent['left_knee_flexion_deg'];pair=next((a,b) for a,b in zip(approved,approved[1:]) if a['joint_dofs']['left_shin']['flexion_extension']<=knee<=b['joint_dofs']['left_shin']['flexion_extension']);a,b=pair;lo=a['joint_dofs']['left_shin']['flexion_extension'];hi=b['joint_dofs']['left_shin']['flexion_extension'];fraction=(knee-lo)/(hi-lo)
            for dof in ('flexion_extension','abduction_adduction'):state['joint_dofs']['left_thigh'][dof]=a['joint_dofs']['left_thigh'][dof]+fraction*(b['joint_dofs']['left_thigh'][dof]-a['joint_dofs']['left_thigh'][dof])
            offset=intent['pelvis_left_displacement'];roles=intent['contact_roles'];record=realize(state,offset,roles)
            if reference is None:reference=record['rear_centers']
            def residual(r):
                a=Vector(r['rear_centers']['left'])-Vector(reference['left']);b=Vector(r['rear_centers']['right'])-Vector(reference['right']);return np.array([a.dot(body.left),a.dot(body.front),b.dot(body.left),b.dot(body.front),sum(r['contact_errors']['right'].values())/2])
            if variant=='candidate':
                for iteration in range(5):
                    error=residual(record)
                    if max(abs(v) for v in error)<body.runtime['metrics']['foot_chain_length']*.001:break
                    current=[state['joint_dofs'][joint][dof] for joint,dof,_,_ in controls];columns=[]
                    for j,(joint,dof,lo,hi) in enumerate(controls):
                        step=.05 if current[j]+.05<=hi else -.05;state['joint_dofs'][joint][dof]=current[j]+step;trial=realize(state,offset,roles);columns.append((residual(trial)-error)/step);state['joint_dofs'][joint][dof]=current[j]
                    try:correction=np.linalg.solve(np.column_stack(columns),error)
                    except np.linalg.LinAlgError:raise RuntimeError('Degenerate transfer IK')
                    accepted=False
                    for scale in (1.,.5,.25,.125,.0625):
                        for j,(joint,dof,lo,hi) in enumerate(controls):state['joint_dofs'][joint][dof]=max(lo,min(hi,current[j]-scale*float(correction[j])))
                        try:trial=realize(state,offset,roles)
                        except ValueError:
                            continue
                        if np.linalg.norm(residual(trial))<np.linalg.norm(error):record=trial;accepted=True;break
                    if not accepted:raise RuntimeError('No improving transfer step inside unchanged preferred envelopes')
                if record['contact_max_abs']>body.runtime['contact_tolerance']:failures.append({'frame':i,'gate':'unchanged_bilateral_contact','error':record['contact_max_abs']})
                if record['balance']['status']!='PASS':failures.append({'frame':i,'gate':'support_balance','margin':record['balance']['signed_balance_margin']})
                for side,a in record['alignment'].items():
                    if a['status']!='PASS':failures.append({'frame':i,'gate':'tracking','side':side,**a})
            error=residual(record);drift=max(math.hypot(*error[:2]),math.hypot(*error[2:4]));record['plant_horizontal_drift']=drift;record['normalized_time']=t;record['intent']=intent
            if variant=='candidate' and drift>body.runtime['metrics']['foot_chain_length']*.05:failures.append({'frame':i,'gate':'plant_drift','error':drift})
            if variant=='candidate':
                now={b.name:b.matrix.to_quaternion().normalized() for b in body.rig.pose.bones}
                if previous and max(math.degrees(previous[n].rotation_difference(q).angle) for n,q in now.items())>30:failures.append({'frame':i,'gate':'joint_step'})
                previous=now
            records[f'{variant}/{i:02d}']=record
            gate.set_view(body.camera,body.center,body.rig,body.canonical,'FRONT',body.scale);body.scene.render.filepath=str(preview/f'{i:02d}.png')
            import bpy
            bpy.ops.render.render(write_still=True)
            if i in keys:
                for col,view in enumerate(('FRONT','THREE_QUARTER','SIDE')):gate.set_view(body.camera,body.center,body.rig,body.canonical,view,body.scale);gate.render_cell(body.scene,cells,keys[i],col,f'frame_{i:02d}',view,420)
            print(f'TRANSFER {variant} {i}/24',flush=True)
    report={'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'machine_status':'FAIL' if failures else 'PASS','ai_visual_status':'NOT_REVIEWED','failures':failures,'samples':records,'source_glb_sha256':body.canonical['source']['sha256'],'camera_scale':body.scale,'scope':'quasistatic planted transfer; TOUCH contact excluded from weightbearing polygon; no force measurement','source_sha256':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),REPO/'tools/ballet_motion/weight_transfer_v1.py',REPO/'tools/blender/bbm_body_runtime_v1.py',REPO/'build/visual_validation/BBM-5/report.json')}}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if failures:raise RuntimeError(str(failures))
if __name__=='__main__':
    try:main()
    except Exception as exc:
        out=REPO/'build/visual_validation/BBM-5/weight-transfer';out.mkdir(parents=True,exist_ok=True)
        if not (out/'report.json').exists():(out/'report.json').write_text(json.dumps({'machine_status':'FAIL','ai_visual_status':'NOT_REVIEWED','fatal_error':str(exc)},indent=2)+'\n')
        raise
