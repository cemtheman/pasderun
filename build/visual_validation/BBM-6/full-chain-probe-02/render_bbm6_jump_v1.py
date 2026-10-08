"""Observed four-state vertical jump; ground constraints stay phase-specific."""
import copy,json,math,sys,hashlib,subprocess,statistics,argparse
from pathlib import Path
from mathutils import Vector,Matrix,Quaternion
import bpy
REPO=Path(__file__).resolve().parents[2];sys.path[:0]=[str(REPO/'tools/blender'),str(REPO/'tools/ballet_motion')]
from bbm_body_runtime_v1 import BodyRuntime,gate,surface_centroid
from render_bbm3_foot_v1 import apply_calibrated_basis
from jump_chain_v1 import jump_intent,jump_review_times
from lower_body_foundation_motion import minimum_jerk
from distributed_turnout_v1 import derive_turnout,alignment_diagnostics
from support_balance_v1 import balance_diagnostics
from weight_transfer_v1 import rotation_step_degrees
from foot_semantics_v1 import foot_state

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=REPO/'build/visual_validation/BBM-6/candidate-01')
    parser.add_argument('--dense',action='store_true');parser.add_argument('--geometry-only',action='store_true')
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    out=args.output;out.mkdir(parents=True,exist_ok=True);(out/'report.json').unlink(missing_ok=True)
    proof=REPO/'build/visual_validation/BBM-5/milestone_report.json'
    if json.loads(proof.read_text())['ai_visual_status']!='AI_VISUAL_PASS':raise RuntimeError('Full BBM-5 required')
    plie_path=REPO/'build/visual_validation/BBM-5/report.json';plie=json.loads(plie_path.read_text());approved=[plie['samples'][f'candidate/{i:02d}']['canonical_state'] for i in range(25)]
    body=BodyRuntime();body.scale*=1.12;records={};failures=[];times=jump_review_times(args.dense)
    keyframes=tuple(sorted(set(min(range(len(times)),key=lambda i:abs(times[i]-t)) for t in ((0,.1,.2,.25,.32,.35,.4,.45,.5,.55,.63,.73,1) if args.dense else (0,12/48,16/48,17/48,24/48,26/48,27/48,36/48,1)))))
    for variant in ('baseline','candidate'):
        cells=out/variant;cells.mkdir(exist_ok=True);preview=cells/'preview';preview.mkdir(exist_ok=True);previous=None;floor=None
        for i,t in enumerate(times):
            intent=jump_intent(t,variant=='candidate');knee=intent['knee_flexion_deg'];state=copy.deepcopy(approved[0]);state['pose']='jump_chain'
            a,b=next((a,b) for a,b in zip(approved,approved[1:]) if a['joint_dofs']['left_shin']['flexion_extension']<=knee<=b['joint_dofs']['left_shin']['flexion_extension']);lo=a['joint_dofs']['left_shin']['flexion_extension'];hi=b['joint_dofs']['left_shin']['flexion_extension'];p=(knee-lo)/(hi-lo)
            for side in ('left','right'):
                for dof in ('flexion_extension','abduction_adduction'):state['joint_dofs'][f'{side}_thigh'][dof]=a['joint_dofs'][f'{side}_thigh'][dof]+p*(b['joint_dofs'][f'{side}_thigh'][dof]-a['joint_dofs'][f'{side}_thigh'][dof])
                state['joint_dofs'][f'{side}_shin']['flexion_extension']=knee;state['turnout'][side].update({'knee_flexion_deg':knee,'knee_external_rotation_deg':derive_turnout(body.constraints,45,knee)['knee_external_rotation_deg']})
            # The unchanged flat solver is a legal seed, never the final jump proof.
            seed=body.realize(state,{'left':'SUPPORT','right':'SUPPORT'});rise=intent['foot_rise_progress'];feet={};matrix_errors={}
            for side in ('left','right'):
                angle=intent['flight_ankle_plantar_deg'] if intent['state']=='FLIGHT' else (1-rise)*seed['foot_proof'][side]['anatomical']['anatomical_plantar_deg']+rise*intent['ground_push_plantar_deg']
                feet[side]=foot_state(body.constraints,'DEMI_POINTE' if rise>0 else 'FLAT',angle,intent['toe_flexion_deg'],0)
                for key,rotation in ((f'{side}_foot',-(body.neutral[side]+angle)),(f'{side}_toes',intent['toe_flexion_deg'])):
                    bone=body.canonical['canonical_bones'][key];parent,rest=gate.static_core.canonical_parent_and_rest_local(body.rig,body.canonical,key);desired=(parent@rest@Matrix.Rotation(math.radians(rotation),3,'X')).to_quaternion().normalized().to_matrix();apply_calibrated_basis(body.rig,bone['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(bone,desired));error=gate.matrix_max_error(gate.static_core.canonical_basis_from_rig_pose(body.rig.pose.bones[bone['rig_bone']],bone),desired);matrix_errors[key]=error
                    if error>body.axis['thresholds']['hierarchy_reconstruction_max_error']:raise RuntimeError('Unchanged foot/toe reconstruction failed')
            regions=('fore',) if rise>0 else ('rear','fore');heights=gate.static_core.contact_heights(body.rig,body.runtime['anchors'],body.up,body.q);shift=statistics.median(body.runtime['rest_heights'][s][r]-heights[s][r] for s in ('left','right') for r in regions);translation=Vector(seed['root_translation'])+body.up*(shift+intent['flight_clearance']);gate.static_core.set_root_translation_armature_space(body.rig,body.canonical['canonical_bones']['pelvis']['rig_bone'],translation)
            trunk={}
            if variant=='candidate':
                push=minimum_jerk((t-.16)/.08)*(1-minimum_jerk((t-.29)/.06))
                landing=minimum_jerk((t-.49)/.07)*(1-minimum_jerk((t-.64)/.08))
                angle=4.6*max(push,landing)
                names=[body.canonical['canonical_bones'][n]['rig_bone'] for n in ('spine_lower','spine_mid')]+['Chest','Clavicle_L','Clavicle_R','Upper_Arm_L','Upper_Arm_R','Lower_Arm_L','Lower_Arm_R','Hand_L','Hand_R','Head']
                originals={n:body.rig.pose.bones[n].matrix.to_quaternion().normalized().to_matrix() for n in names}
                for j,n in enumerate(names):
                    share=1 # whole trunk carriage; neck/arms preserve relative orientation
                    apply_calibrated_basis(body.rig,n,Quaternion(body.left,math.radians(angle*share)).to_matrix()@originals[n])
                chest=body.rig.pose.bones['Chest'];tilt=math.degrees((chest.tail-chest.head).angle(body.up));limit=next(c for c in body.grammar['poses']['plie']['checks'] if c.get('name')=='trunk_tilt_deg')['max']
                trunk={'forward_anticipation_deg':angle,'observed_chest_tilt_deg':tilt,'existing_limit_deg':limit}
                if tilt>limit:failures.append({'frame':i,'gate':'existing_trunk_tilt','error':tilt})
            heights=gate.static_core.contact_heights(body.rig,body.runtime['anchors'],body.up,body.q);errors={s:{r:heights[s][r]-body.runtime['rest_heights'][s][r] for r in regions} for s in ('left','right')};points={};all_points=[]
            for side in ('left','right'):
                ps=[]
                for region in ('rear','fore'):
                    evaluated=gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][side][region]);all_points+=evaluated
                    if region in regions:ps+=sorted(evaluated,key=lambda p:p.dot(body.up))[:max(3,int(len(evaluated)*body.q))]
                points[side]=[(p.dot(body.left),p.dot(body.front)) for p in ps]
            if floor is None:floor=min(p.dot(body.up) for p in all_points)
            clearance=min(p.dot(body.up)-floor for p in all_points);com,area=surface_centroid(body.rig);air=intent['state']=='FLIGHT';balance={'status':'NOT_APPLICABLE_FLIGHT','reason':'no ground support; not a static balance assertion'} if air else balance_diagnostics(points,(com.dot(body.left),com.dot(body.front)),{'left':'SUPPORT','right':'SUPPORT'})
            alignment={}
            if not air:
                for side in ('left','right'):
                    shin=body.canonical['canonical_bones'][f'{side}_shin'];toe=body.canonical['canonical_bones'][f'{side}_toes'];heading=gate.static_core.canonical_basis_from_rig_pose(body.rig.pose.bones[shin['rig_bone']],shin).col[2];ray=body.rig.pose.bones[toe['rig_bone']].tail-body.rig.pose.bones[toe['rig_bone']].head;alignment[side]=alignment_diagnostics(body.constraints,list(heading),list(ray),list(body.front),list(body.up))
            now={b.name:b.matrix.to_quaternion().normalized() for b in body.rig.pose.bones};step=max((rotation_step_degrees(tuple(previous[n]),tuple(q)) for n,q in now.items()),default=0) if previous else 0;previous=now
            root=body.rig.pose.bones[body.canonical['canonical_bones']['pelvis']['rig_bone']];actual=root.head-root.bone.head_local;root_error=(actual-translation).length
            record={'trunk':trunk,'intent':intent,'canonical_state':state,'foot_anatomy':feet,'foot_matrix_errors':matrix_errors,'contact_policy':'NONE_FLIGHT' if air else 'FOREFOOT' if rise>0 else 'FULL_FOOT','support_roles':{'left':'NONE','right':'NONE'} if air else {'left':'SUPPORT','right':'SUPPORT'},'contact_errors':errors,'root_translation':list(translation),'observed_root_error':root_error,'minimum_foot_clearance':clearance,'surface_centroid':list(com),'surface_area':area,'balance':balance,'alignment':alignment,'joint_step_deg':step,'wrist':gate.validate_hand_axial_continuity(body.rig,body.canonical,body.constraints,body.visual)}
            if variant=='candidate':
                if root_error>1e-7:failures.append({'frame':i,'gate':'root_realization','error':root_error})
                if step>30:failures.append({'frame':i,'gate':'joint_step','error':step})
                if air:
                    if clearance<=0:failures.append({'frame':i,'gate':'flight_clearance','error':clearance})
                    if max(abs(e-intent['flight_clearance']) for v in errors.values() for e in v.values())>body.runtime['contact_tolerance']:failures.append({'frame':i,'gate':'clearance_realization'})
                else:
                    if max(abs(e) for v in errors.values() for e in v.values())>body.runtime['contact_tolerance']:failures.append({'frame':i,'gate':'unchanged_ground_contact'})
                    if balance['status']!='PASS':failures.append({'frame':i,'gate':'support_balance','margin':balance['signed_balance_margin']})
                    for side,a in alignment.items():
                        if a['status']!='PASS':failures.append({'frame':i,'gate':'tracking','side':side,**a})
                    if intent['state']=='LANDING' and .55<=t<=.5625 and knee<8:failures.append({'frame':i,'gate':'straight_knee_impact'})
            records[f'{variant}/{i:02d}']=record
            record['time_normalized']=t
            if args.geometry_only:continue
            gate.set_view(body.camera,body.center,body.rig,body.canonical,'FRONT',body.scale);body.scene.render.filepath=str(preview/f'{i:02d}.png');bpy.ops.render.render(write_still=True)
            if i in keyframes:
                for col,view in enumerate(('FRONT','THREE_QUARTER','SIDE')):gate.set_view(body.camera,body.center,body.rig,body.canonical,view,body.scale);gate.render_cell(body.scene,cells,keyframes.index(i),col,f'frame_{i:02d}',view,420)
            print(f'JUMP {variant} {i}/{len(times)-1} {intent["state"]}',flush=True)
    report={'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'machine_status':'FAIL' if failures else 'PASS','ai_visual_status':'NOT_REVIEWED','failures':failures,'samples':records,'camera_scale':body.scale,'source_glb_sha256':body.canonical['source']['sha256'],'scope':'four-state kinematic vertical jump; ground support invariant only during contact; no force simulation','source_sha256':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),REPO/'tools/ballet_motion/jump_chain_v1.py',REPO/'tools/blender/bbm_body_runtime_v1.py',plie_path,proof)}};(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    report.update({'sample_times':times,'keyframe_indices':keyframes,'geometry_only':args.geometry_only});(out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if failures:raise RuntimeError(str(failures))
if __name__=='__main__':main()
