"""Measure new BBM-7 composition using unchanged physical authorities."""
import argparse,copy,json,hashlib,math,sys,subprocess
from pathlib import Path
import bpy
from mathutils import Quaternion,Vector
REPO=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(REPO/'tools/blender'),str(REPO/'tools/ballet_motion')]
from bbm_body_runtime_v1 import BodyRuntime,gate,surface_centroid
from bbm_phrase_runtime_v1 import realize_transfer
from phrase_v1 import phrase_intent,review_times,BOUNDARIES,STYLES
from distributed_turnout_v1 import derive_turnout
from weight_transfer_v1 import rotation_step_degrees,transfer_intent,weightbearing_roles
from support_balance_v1 import balance_diagnostics
from render_bbm3_foot_v1 import apply_calibrated_basis

def state_at(rows,p):
    x=p*(len(rows)-1);lo=min(len(rows)-1,int(x));hi=min(len(rows)-1,lo+1);w=x-lo
    state=copy.deepcopy(rows[lo])
    for joint,values in state['joint_dofs'].items():
        for dof,a in values.items():values[dof]=a+(rows[hi]['joint_dofs'][joint][dof]-a)*w
    return state

def upper_at(rows,p):
    x=24*p;lo=min(24,int(x));hi=min(24,lo+1);w=x-lo
    return {n:list(Quaternion(q).slerp(Quaternion(rows[hi]['orientations_wxyz'][n]),w))
            for n,q in rows[lo]['orientations_wxyz'].items()}

def couple_wrist(body,rows,p):
    """Interpolate existing wrist DOFs, never an independent axial hand roll."""
    for n in ('Chest','Clavicle_L','Clavicle_R','Upper_Arm_L','Upper_Arm_R',
              'Lower_Arm_L','Lower_Arm_R','Hand_L','Hand_R','Head'):
        apply_calibrated_basis(body.rig,n,Quaternion(body.upper[n]).to_matrix())
    x=24*p;lo=min(24,int(x));hi=min(24,lo+1);w=x-lo
    for side in ('left','right'):
        values=[]
        for dof in ('flexion_extension','radial_ulnar_deviation'):
            a=rows[lo]['wrist'][side][dof+'_deg'];b=rows[hi]['wrist'][side][dof+'_deg']
            value=a+(b-a)*w;limit=body.constraints['joint_limits']['wrist_2dof']['dofs'][dof]['preferred']
            values.append(max(limit['min'],min(limit['max'],value)))
        key=f'{side}_hand';bone=body.canonical['canonical_bones'][key]
        parent,rest=gate.static_core.canonical_parent_and_rest_local(body.rig,body.canonical,key)
        desired=(parent@rest@gate.static_core.wrist_delta_matrix(*values)).to_quaternion().normalized().to_matrix()
        apply_calibrated_basis(body.rig,bone['rig_bone'],gate.static_core.rig_basis_from_canonical_pose(bone,desired))
        body.upper[bone['rig_bone']]=list(body.rig.pose.bones[bone['rig_bone']].matrix.to_quaternion().normalized())

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--geometry-only',action='store_true');parser.add_argument('--styles',nargs='+',choices=tuple(STYLES),default=['clear','soft'])
    args=parser.parse_args(sys.argv[sys.argv.index('--')+1:]);out=args.output
    if out.exists():raise RuntimeError('Refuse to overwrite evidence; use fresh output')
    out.mkdir(parents=True);load=lambda p:json.loads(p.read_text())
    plie_path=REPO/'build/visual_validation/BBM-5/report.json';transfer_path=REPO/'build/visual_validation/BBM-5/weight-transfer/report.json';upper_path=REPO/'build/visual_validation/BBM-1/elbow-path/report.json'
    plie=[load(plie_path)['samples'][f'candidate/{i:02d}']['canonical_state'] for i in range(25)]
    transfer=[load(transfer_path)['samples'][f'candidate/{i:02d}']['canonical_state'] for i in range(25)]
    upper=load(upper_path)['samples'];body=BodyRuntime();times=review_times();records={};failures=[]
    # Both styles have exactly identical camera, source, lighting and geometry policies.
    body.scale*=1.12
    key_times=(0,.1,.2,.28,.4,.48,.52,.56,.68,.8,.9,1)
    keys=sorted({min(range(len(times)),key=lambda i:abs(times[i]-t)) for t in key_times})
    reference=None
    for style in args.styles:
        cells=out/style;cells.mkdir();last=None;roots={};head_targets={}
        for i,t in enumerate(times):
            intent=phrase_intent(t,style);coord=intent['transfer_coordinate']
            state=state_at(plie,intent['plie_coordinate']) if intent['primitive'] in ('PLIE','CLOSURE') else state_at(transfer,coord)
            for side in ('left','right'):
                knee=state['joint_dofs'][f'{side}_shin']['flexion_extension']
                hip=state['joint_dofs'][f'{side}_thigh']['internal_external_rotation']
                state['turnout'][side].update(derive_turnout(body.constraints,hip,knee))
            body.upper=upper_at(upper,intent['arm_coordinate'])
            couple_wrist(body,upper,intent['arm_coordinate'])
            offset=transfer_intent(coord)['pelvis_left_displacement']
            record=realize_transfer(body,state,offset,intent['roles'])
            head=body.rig.pose.bones['Head'];rotation=Quaternion(body.up,math.radians(intent['head_yaw_deg']))
            apply_calibrated_basis(body.rig,'Head',rotation.to_matrix()@head.matrix.to_quaternion().normalized().to_matrix())
            # Recompute geometry COM after ALL upper/head style changes.
            points={}
            for side in ('left','right'):
                selected=[]
                for region in ('rear','fore'):
                    ps=sorted(gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][side][region]),key=lambda p:p.dot(body.up))
                    selected+=ps[:max(3,int(len(ps)*body.q))]
                points[side]=[(p.dot(body.left),p.dot(body.front)) for p in selected]
            com,area=surface_centroid(body.rig)
            record['balance']=balance_diagnostics(points,(com.dot(body.left),com.dot(body.front)),weightbearing_roles(intent['roles']))
            record['surface_centroid']=list(com)
            elbow={}
            for side in ('left','right'):
                names=body.canonical['canonical_bones']
                a=body.rig.pose.bones[names[f'{side}_upper_arm']['rig_bone']]
                b=body.rig.pose.bones[names[f'{side}_forearm']['rig_bone']]
                value=math.degrees((a.tail-a.head).angle(b.tail-b.head))
                bounds=body.constraints['joint_limits']['elbow_twist']['dofs']['flexion_extension']['preferred']
                elbow[side]=value
                if not bounds['min']<=value<=bounds['max']:failures.append({'style':style,'time':t,'gate':'elbow_preferred','side':side,'error':value})
            record['elbow_flexion_deg']=elbow
            centers={}
            for side in ('left','right'):
                centers[side]={}
                for region in ('rear','fore'):
                    ps=gate.static_core.evaluated_sample_points(body.rig,body.runtime['anchors'][side][region])
                    centers[side][region]=list(sum(ps,Vector())/len(ps))
            if reference is None:reference=copy.deepcopy(centers)
            drift=max(math.hypot((Vector(c)-Vector(reference[s][r])).dot(body.left),(Vector(c)-Vector(reference[s][r])).dot(body.front)) for s,v in centers.items() for r,c in v.items())
            limit=body.runtime['metrics']['foot_chain_length']*.05
            if drift>limit:failures.append({'style':style,'time':t,'gate':'plant_drift','error':drift,'limit':limit})
            if record['contact_max_abs']>body.runtime['contact_tolerance']:failures.append({'style':style,'time':t,'gate':'contact','error':record['contact_max_abs']})
            if record['balance']['status']!='PASS':failures.append({'style':style,'time':t,'gate':'balance','margin':record['balance']['signed_balance_margin']})
            for side,a in record['alignment'].items():
                if a['status']!='PASS':failures.append({'style':style,'time':t,'gate':'alignment','side':side,**a})
            now={b.name:list(b.matrix.to_quaternion().normalized()) for b in body.rig.pose.bones}
            step=max((rotation_step_degrees(last[n],q) for n,q in now.items()),default=0) if last else 0.
            if step>30:failures.append({'style':style,'time':t,'gate':'joint_step','error':step})
            last=now;root=body.rig.pose.bones['Hips'];roots[t]=list(root.head-root.bone.head_local)
            record.update({'time':t,'intent':intent,'orientations_wxyz':now,'root_translation':roots[t],'plant_drift':drift,'plant_limit':limit,'joint_step_deg':step})
            records[f'{style}/{i:03d}']=record
            if not args.geometry_only:
                preview=cells/'preview';preview.mkdir(exist_ok=True)
                gate.set_view(body.camera,body.center,body.rig,body.canonical,'FRONT',body.scale);body.scene.render.filepath=str(preview/f'{i:03d}.png');bpy.ops.render.render(write_still=True)
                if i in keys:
                    for col,view in enumerate(('FRONT','THREE_QUARTER','SIDE')):
                        gate.set_view(body.camera,body.center,body.rig,body.canonical,view,body.scale);gate.render_cell(body.scene,cells,keys.index(i),col,f'frame_{i:03d}',view,420)
            print('BBM7',style,i,len(times),t,flush=True)
        for t in BOUNDARIES:
            a=min(roots,key=lambda v:abs(v-(t-1e-6)));b=min(roots,key=lambda v:abs(v-(t+1e-6)))
            step=math.dist(roots[a],roots[b])
            if step>1e-4:failures.append({'style':style,'time':t,'gate':'boundary_root','error':step,'limit':1e-4})
    sources=[Path(__file__),REPO/'tools/blender/bbm_phrase_runtime_v1.py',REPO/'tools/ballet_motion/phrase_v1.py',REPO/'tools/blender/bbm_body_runtime_v1.py',plie_path,transfer_path,upper_path]
    report={'machine_status':'FAIL' if failures else 'PASS','ai_visual_status':'NOT_REVIEWED','git_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'source_glb_sha256':body.canonical['source']['sha256'],'source_sha256':{str(p.relative_to(REPO)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},'samples':records,'failures':failures,'times':times,'keyframe_indices':keys,'camera_scale':body.scale,'geometry_only':args.geometry_only,'scope':'new quasistatic planted phrase; composed physical states independently measured'}
    (out/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    print('BBM7 MACHINE',report['machine_status'],len(failures),flush=True)

if __name__=='__main__':
    try:main()
    except Exception as exc:
        if '--output' in sys.argv:
            out=Path(sys.argv[sys.argv.index('--output')+1])
            if out.exists():
                (out/'fatal_failure.json').write_text(json.dumps({'machine_status':'FAIL','ai_visual_status':'NOT_REVIEWED','error':str(exc)})+'\n')
        raise
