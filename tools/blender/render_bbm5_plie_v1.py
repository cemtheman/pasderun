"""Deterministic 49-sample plié descent/return on accepted physical layers."""
import copy,json,hashlib,subprocess,sys,math
from pathlib import Path
from mathutils import Vector
REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'tools/blender'),str(REPO/'tools/ballet_motion')]
from bbm_body_runtime_v1 import BodyRuntime,gate
from plie_chain_v1 import chain_intent,plie_progress
from distributed_turnout_v1 import derive_turnout

def main():
    out=REPO/'build/visual_validation/BBM-5';out.mkdir(parents=True,exist_ok=True);(out/'report.json').unlink(missing_ok=True)
    prior=json.loads((REPO/'build/visual_validation/BBM-4/report.json').read_text())
    if prior['ai_visual_status']!='AI_VISUAL_PASS':raise RuntimeError('BBM-4 required')
    body=BodyRuntime();base=prior['fixtures']['candidate/flat']['canonical_state'];end=json.loads((REPO/'build/visual_validation/BBM-2/report.json').read_text())['fixtures']['candidate/plie']['authority']['closed_stance']['hip_adduction_deg'];records={};failures=[];keys={0:0,12:1,24:2,36:3,48:4}
    for variant in ('baseline','candidate'):
        cells=out/variant;cells.mkdir(exist_ok=True);preview=cells/'preview';preview.mkdir(exist_ok=True)
        for p in cells.rglob('*.png'):p.unlink()
        reference=None;last_root=None;previous_basis={}
        for i in range(49):
            t=i/48;intent=chain_intent(t);p=plie_progress(t);state=copy.deepcopy(base);state['pose']='plie_chain';roles={'left':'SUPPORT','right':'SUPPORT'}
            for side in roles:
                state['joint_dofs'][f'{side}_shin']['flexion_extension']=intent['knee_flexion_deg']
                state['joint_dofs'][f'{side}_thigh'].update({'flexion_extension':base['joint_dofs'][f'{side}_thigh']['flexion_extension']*(1-p)+(intent['hip_reference_flexion_deg'] if variant=='candidate' else 18*p),'abduction_adduction':base['joint_dofs'][f'{side}_thigh']['abduction_adduction']+(end-base['joint_dofs'][f'{side}_thigh']['abduction_adduction'])*(intent['closure_progress'] if variant=='candidate' else p)})
                state['turnout'][side].update({'knee_flexion_deg':intent['knee_flexion_deg'],'knee_external_rotation_deg':derive_turnout(body.constraints,45,intent['knee_flexion_deg'])['knee_external_rotation_deg']})
            record=body.realize(state,roles)
            def rear_centers():
                return {s:sum(gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][s]['rear']),Vector())/len(body.runtime['anchors'][s]['rear']) for s in roles}
            centers=rear_centers()
            if reference is None:reference={s:list(centers[s]) for s in roles}
            if variant=='candidate' and i not in (0,48):
                # Contact-aware IK with bounded hip variables; no root lateral shift.
                controls=[('abduction_adduction',-12.,20.),('flexion_extension',-12.,32.)]
                # Bounded 2x2 local Jacobian solve; every trial still passes the
                # complete anatomical/contact runtime. Coupling is measured.
                for it in range(3):
                    current=[state['joint_dofs']['left_thigh'][d] for d,_,_ in controls]
                    delta=centers['left']-Vector(reference['left']);error=[delta.dot(body.left),delta.dot(body.front)]
                    if math.hypot(*error)<body.runtime['metrics']['foot_chain_length']*.001:break
                    columns=[]
                    for j,(dof,lo,hi) in enumerate(controls):
                        step=.05 if current[j]+.05<=hi else -.05
                        for side in roles:state['joint_dofs'][f'{side}_thigh'][dof]=current[j]+step
                        body.realize(state,roles);trial=rear_centers()['left'];difference=trial-centers['left'];columns.append([difference.dot(body.left)/step,difference.dot(body.front)/step])
                        for side in roles:state['joint_dofs'][f'{side}_thigh'][dof]=current[j]
                    a,c=columns[0];b,d=columns[1];det=a*d-b*c
                    if abs(det)<1e-10:raise RuntimeError('Degenerate contact IK Jacobian')
                    correction=[(d*error[0]-b*error[1])/det,(-c*error[0]+a*error[1])/det]
                    for j,(dof,lo,hi) in enumerate(controls):
                        value=max(lo,min(hi,current[j]-correction[j]))
                        for side in roles:state['joint_dofs'][f'{side}_thigh'][dof]=value
                    record=body.realize(state,roles);centers=rear_centers()
            drift=max(math.hypot((centers[s]-Vector(reference[s])).dot(body.left),(centers[s]-Vector(reference[s])).dot(body.front)) for s in roles)
            record['rear_anchor_horizontal_drift']=drift;record['canonical_state']=copy.deepcopy(state);record['normalized_time']=t;record['intent']=intent
            if variant=='candidate':
                if record['balance']['status']!='PASS':failures.append({'frame':i,'gate':'balance','margin':record['balance']['signed_balance_margin']})
                if drift>body.runtime['metrics']['foot_chain_length']*.05:failures.append({'frame':i,'gate':'support_anchor_drift','value':drift})
                for s,a in record['alignment'].items():
                    if a['status']!='PASS':failures.append({'frame':i,'gate':'tracking','side':s,**a})
                root=record['root_translation'][2]
                if last_root is not None and ((i<=24 and root>last_root+1e-4) or (i>24 and root<last_root-1e-4)):failures.append({'frame':i,'gate':'root_descent_return_monotonic'})
                last_root=root
                for bone in body.rig.pose.bones:
                    q=bone.matrix.to_quaternion().normalized()
                    if bone.name in previous_basis and math.degrees(previous_basis[bone.name].rotation_difference(q).angle)>30:failures.append({'frame':i,'gate':'joint_step','bone':bone.name})
                    previous_basis[bone.name]=q.copy()
            records[f'{variant}/{i:02d}']=record
            gate.set_view(body.camera,body.center,body.rig,body.canonical,'FRONT',body.scale);body.scene.render.filepath=str(preview/f'{i:02d}.png');body.scene.render.resolution_x=420;body.scene.render.resolution_y=420
            import bpy
            bpy.ops.render.render(write_still=True)
            if i in keys:
                for col,view in enumerate(('FRONT','THREE_QUARTER','SIDE')):gate.set_view(body.camera,body.center,body.rig,body.canonical,view,body.scale);gate.render_cell(body.scene,cells,keys[i],col,f'frame_{i:02d}',view,420)
            print(f'BBM-5 {variant} sample{i}/48',flush=True)
    report={'git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'machine_status':'FAIL' if failures else 'PASS','ai_visual_status':'NOT_REVIEWED','failures':failures,'samples':records,'source_glb_sha256':body.canonical['source']['sha256'],'camera_scale':body.scale,'source_sha256':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__),REPO/'tools/blender/bbm_body_runtime_v1.py',REPO/'tools/ballet_motion/plie_chain_v1.py',REPO/'build/visual_validation/BBM-4/report.json')}}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    if failures:raise RuntimeError(str(failures))
if __name__=='__main__':
    try:main()
    except Exception as exc:
        out=REPO/'build/visual_validation/BBM-5';out.mkdir(parents=True,exist_ok=True)
        if not (out/'report.json').exists():(out/'report.json').write_text(json.dumps({'machine_status':'FAIL','ai_visual_status':'NOT_REVIEWED','fatal_error':str(exc)},indent=2)+'\n')
        raise
