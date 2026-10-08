"""Independently audit actual Godot-observed poses on immutable source skin.
This is runtime transform replay for mesh measurement, NOT a Blender render or
regeneration of accepted BBM evidence. All inherited thresholds stay unchanged.
"""
import bpy,json,sys,math,hashlib,copy
from pathlib import Path
from mathutils import Matrix,Quaternion,Vector
ROOT=Path(__file__).resolve().parents[2]
args=sys.argv[sys.argv.index('--')+1:]; OUT=Path(args[0]); observed=json.loads((OUT/'runtime.json').read_text())
sys.path[:0]=[str(ROOT/'tools/blender'),str(ROOT/'tools/ballet_motion')]
import render_foundation_pose_visual_gate_v1 as gate
from bbm_body_runtime_v1 import surface_centroid
sys.path.insert(0,str(ROOT/"tools/blender/motion_studio"))
from accepted_arm_visual_v0_6 import measured_hand_mesh_projection
from support_balance_v1 import balance_diagnostics
from distributed_turnout_v1 import alignment_diagnostics
from anatomical_constraints import knee_external_rotation_cap_deg
from foot_semantics_v1 import anatomical_plantar_from_canonical
from weight_transfer_v1 import rotation_step_degrees,weightbearing_roles
payload=json.loads((ROOT/'assets/bbm8/clear6s_runtime_candidate.json').read_text())
hand_calibration=json.loads((ROOT/'build/visual_validation/BBM-1/calibration.json').read_text())
canonical={'canonical_bones':payload['canonical'],'body_frame':{'declared_axes_armature_local':{'up':[0,0,1],'front':[0,-1,0],'left':[1,0,0]}}}
static=json.loads((ROOT/'assets/ballet_motion/static_rig_application_contract_v1.json').read_text())
constraints=json.loads((ROOT/'assets/ballet_motion/anatomical_constraints_v1.json').read_text())
visual_contract=json.loads((ROOT/'assets/ballet_motion/foundation_pose_visual_gate_v1.json').read_text())
neutral=json.loads((ROOT/'build/visual_validation/BBM-3/report.json').read_text())['ankle_neutral_offset_deg']
source=ROOT/'assets/characters/low_poly_girl/low_poly_girl .glb'
assert hashlib.sha256(source.read_bytes()).hexdigest()==payload['source_glb_sha256']
bpy.ops.wm.read_factory_settings(use_empty=True);bpy.ops.import_scene.gltf(filepath=str(source));rig=next(o for o in bpy.context.scene.objects if o.type=='ARMATURE')
for obj in bpy.context.scene.objects:
 if obj.animation_data:obj.animation_data_clear()
contact=gate.prepare_contact_runtime(rig,canonical,static)
C=Matrix(((1,0,0),(0,0,1),(0,-1,0)))
up=Vector((0,0,1));front=Vector((0,-1,0));left=Vector((1,0,0));q=contact['sampling']['low_height_quantile']
records=[];failures=[];refs={};previous=None;previous_roles={};active_reference={}
limits={'contact':contact['contact_tolerance'],'plant':contact['metrics']['foot_chain_length']*.05,'tracking_deg':6,'trunk_deg':10,'reconstruction':1e-5,'joint_step_deg':30,'root_boundary':1e-4}
def fail(row,name,value,limit):failures.append({'frame':row['frame'],'phase':row['phase'],'gate':name,'value':value,'limit':limit})
def angles_xzy(d):
 return (math.degrees(math.atan2(d[2][1],d[1][1])),math.degrees(math.asin(max(-1,min(1,-d[0][1])))),math.degrees(math.atan2(d[0][2],d[0][0])))
def check_dofs(row,joint,values,label):
 for name,value in values.items():
  bounds=constraints['joint_limits'][joint]['dofs'][name]['preferred']
  if value<bounds['min']-.001 or value>bounds['max']+.001:fail(row,'preferred_'+label+'_'+name,value,bounds)
def arm_roll(basis,front_axis,up_axis):
 y=basis.col[1].normalized();z=front_axis-y*front_axis.dot(y)
 if z.length<1e-8:z=up_axis-y*up_axis.dot(y)
 z.normalize();x=y.cross(z).normalized();base=Matrix((list(x),list(y),list(z))).transposed();d=base.transposed()@basis
 roll=math.degrees(math.atan2(d[0][2],d[0][0]));reconstructed=base@Matrix.Rotation(math.radians(roll),3,'Y')
 error=max(abs(reconstructed[i][j]-basis[i][j]) for i in range(3) for j in range(3))
 return roll,error

def points_geometry():
 centers={};support={};heights={}
 for side in ('left','right'):
  centers[side]={};support[side]=[];heights[side]={}
  for region in ('rear','fore'):
   points=gate.static_core.evaluated_sample_points(rig,contact['anchors'][side][region]);centers[side][region]=sum(points,Vector())/len(points)
   heights[side][region]=gate.static_core.quantile([p.dot(up) for p in points],q)
   low=sorted(points,key=lambda p:p.dot(up))[:max(3,int(len(points)*q))]
   support[side]+=[(p.dot(left),p.dot(front)) for p in low]
 return centers,support,heights
for row in observed['observations']:
 phase=row['phase']
 if phase not in ('ENTRY','ACTIVE','EXIT'):continue
 transforms=[]
 for record,p in zip(payload['bones'],row['bones']):
  rot=C.inverted()@Quaternion((p[3],p[0],p[1],p[2])).to_matrix()@Matrix(record['right_bind']).inverted()
  t=rot.to_4x4();t.translation=C.inverted()@Vector(p[4:]);transforms.append(t)
 for i,(record,t) in enumerate(zip(payload['bones'],transforms)):
  bone=rig.pose.bones[record['blender_name']];parent=record['parent'];rest=bone.bone.matrix_local
  local=rest.inverted()@t if parent<0 else rest.inverted()@bone.parent.bone.matrix_local@transforms[parent].inverted()@t
  bone.matrix_basis=local
 bpy.context.view_layer.update()
 roundtrip=max(max(abs(rig.pose.bones[b['blender_name']].matrix[i][j]-t[i][j]) for i in range(4) for j in range(4)) for b,t in zip(payload['bones'],transforms))
 if roundtrip>1e-5:fail(row,'runtime_replay_reconstruction',roundtrip,1e-5)
 centers,points,heights=points_geometry()
 if not refs:refs=copy.deepcopy(centers)
 contact_error_all=max(abs(heights[s][r]-contact['rest_heights'][s][r]) for s in ('left','right') for r in ('rear','fore'))
 global_drift=max(math.hypot((centers[s][r]-refs[s][r]).dot(left),(centers[s][r]-refs[s][r]).dot(front)) for s in ('left','right') for r in ('rear','fore'))
 com,area=surface_centroid(rig)
 normalized=max(0,min(1,(row['elapsed']-float(row.get('entry_seconds',1.2)))/6))
 roles=row.get('contact_roles') or ({'left':'SUPPORT','right':'TOUCH' if .48<=normalized<=.56 else 'SUPPORT'} if phase=='ACTIVE' else {'left':'SUPPORT','right':'SUPPORT'})
 for side in ('left','right'):
  if roles[side] != 'SWING' and previous_roles.get(side)=='SWING':refs[side]=copy.deepcopy(centers[side])
 previous_roles=roles.copy()
 active=[side for side in ('left','right') if roles[side]!='SWING']
 contact_error=max(abs(heights[s][r]-contact['rest_heights'][s][r]) for s in active for r in ('rear','fore'))
 drift=max(math.hypot((centers[s][r]-refs[s][r]).dot(left),(centers[s][r]-refs[s][r]).dot(front)) for s in active for r in ('rear','fore'))
 balance=balance_diagnostics(points,(com.dot(left),com.dot(front)),roles if 'SWING' in roles.values() else weightbearing_roles(roles))
 if contact_error>limits['contact']:fail(row,'full_foot_contact',contact_error,limits['contact'])
 if drift>limits['plant']:fail(row,'full_foot_plant_drift',drift,limits['plant'])
 if balance['signed_balance_margin']<=0:fail(row,'positive_support_margin',balance['signed_balance_margin'],0)
 wrist={}
 try:wrist=gate.validate_hand_axial_continuity(rig,canonical,constraints,visual_contract)
 except Exception as exc:fail(row,'wrist_2dof_preferred_reconstruction',str(exc),'unchanged existing envelope and reconstruction <=1e-5')
 tracking={};ankles={};elbows={};lower_dofs={};upper_dofs={};chain_error=0.
 for i,b in enumerate(payload['bones']):
  if b['parent']<0 or b['blender_name'] not in {canonical['canonical_bones'][side+'_'+joint]['rig_bone'] for side in ('left','right') for joint in ('thigh','shin','foot','toes')}:continue
  parent=b['parent'];expected=(Matrix(payload['bones'][parent]['blender_rest']).inverted()@Matrix(b['blender_rest'])).translation.length
  actual=(transforms[parent].inverted()@transforms[i]).translation.length
  chain_error=max(chain_error,abs(actual-expected))
 if chain_error>1e-5:fail(row,'leg_foot_chain_length_preserved',chain_error,1e-5)
 for side in ('left','right'):
  names=canonical['canonical_bones']
  sign=1 if side=='left' else -1
  hip=gate.canonical_local_delta(rig,canonical,side+'_thigh')
  hd={'flexion_extension':math.degrees(math.atan2(hip[2][1],hip[1][1])), 'abduction_adduction':math.degrees(math.asin(max(-1,min(1,-hip[0][1]))))/sign,'internal_external_rotation':-math.degrees(math.atan2(hip[0][2],hip[0][0]))/sign}
  kd=gate.canonical_local_delta(rig,canonical,side+'_shin');knee=-math.degrees(math.atan2(kd[2][1],kd[1][1]))
  td=gate.canonical_local_delta(rig,canonical,side+'_toes');toe_flex=math.degrees(math.atan2(td[2][1],td[2][2]))
  knee_external=-math.degrees(math.atan2(kd[0][2],kd[0][0]))/sign
  cap=knee_external_rotation_cap_deg(constraints,max(0,knee))
  if knee_external < -.001 or knee_external>cap+.001:fail(row,'derived_knee_rotation_cap_'+side,knee_external,cap)
  lower_dofs[side]={'hip':hd,'knee_flexion':knee,'knee_external':knee_external,'knee_rotation_cap':cap,'toe_flexion':toe_flex}
  for joint,values in [('hip_ball',hd),('knee_hinge',{'flexion_extension':knee}),('mtp_hinge',{'toe_flexion_extension':toe_flex})]:
   for name,value in values.items():
    bounds=constraints['joint_limits'][joint]['dofs'][name]['preferred']
    if value<bounds['min']-.001 or value>bounds['max']+.001:fail(row,'preferred_'+side+'_'+joint+'_'+name,value,bounds)
  shin=names[side+'_shin'];toe=names[side+'_toes'];heading=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[shin['rig_bone']],shin).col[2];tb=rig.pose.bones[toe['rig_bone']];ray=tb.tail-tb.head
  tracking[side]=alignment_diagnostics(constraints,list(heading),list(ray),list(front),list(up))['observed_knee_toe_error_deg']
  if tracking[side]>6:fail(row,'knee_toe_tracking_'+side,tracking[side],6)
  delta=gate.canonical_local_delta(rig,canonical,side+'_foot');raw=gate.static_core.extract_exact_ankle_plantar(delta);inversion=gate.static_core.extract_exact_ankle_inversion(delta,side)
  ankles[side]=anatomical_plantar_from_canonical(constraints,raw,neutral[side])
  check_dofs(row,'ankle_2dof',{'inversion_eversion':inversion},side+'_ankle')
  if ankles[side]['status']!='PASS':fail(row,'ankle_preferred_'+side,ankles[side],'unchanged preferred envelope')
  a=rig.pose.bones[names[side+'_upper_arm']['rig_bone']];b=rig.pose.bones[names[side+'_forearm']['rig_bone']];elbow=math.degrees((a.tail-a.head).angle(b.tail-b.head));elbows[side]=elbow
  preferred=constraints['joint_limits']['elbow_twist']['dofs']['flexion_extension']['preferred']
  if not preferred['min']<=elbow<=preferred['max']:fail(row,'elbow_preferred_'+side,elbow,preferred)
 chest=rig.pose.bones['Chest']
 cb=canonical['canonical_bones']['chest'];cp=gate.static_core.canonical_basis_from_rig_pose(chest,cb);transport=cp@Matrix(cb['canonical_rest_contract']['basis_armature_local']).transposed()
 transported_front=transport@front;transported_up=transport@up;transported_left=transport@left
 for side in ('left','right'):
  sign=1 if side=='left' else -1;arm=canonical['canonical_bones'][side+'_upper_arm'];forearm=canonical['canonical_bones'][side+'_forearm']
  upper=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[arm['rig_bone']],arm);lower=gate.static_core.canonical_basis_from_rig_pose(rig.pose.bones[forearm['rig_bone']],forearm)
  ray=upper.col[1].normalized();flex=math.degrees(math.atan2(ray.dot(transported_front),-ray.dot(transported_up)));abduction=math.degrees(math.asin(max(-1,min(1,sign*ray.dot(transported_left)))))
  roll,err=arm_roll(upper,transported_front,transported_up);pronation,forearm_err=arm_roll(lower,transported_front,transported_up)
  if max(err,forearm_err)>1e-5:fail(row,'upper_arm_roll_reconstruction',max(err,forearm_err),1e-5)
  dofs={'flexion_extension':flex,'abduction_adduction':abduction,'internal_external_rotation':roll};upper_dofs[side]={'shoulder':dofs,'forearm_pronation':pronation,'roll_reconstruction_error':max(err,forearm_err)}
  check_dofs(row,'shoulder_ball',dofs,side+'_shoulder')
  check_dofs(row,'elbow_twist',{'pronation_supination':pronation},side+'_forearm')
 for key in ('spine_lower','spine_mid','chest','neck','head','left_clavicle','right_clavicle'):
  bone=canonical['canonical_bones'][key];a,b,c=angles_xzy(gate.canonical_local_delta(rig,canonical,key))
  values={'flexion_extension':a,'lateral_flexion':b,'axial_rotation':c} if bone['joint_class'] in ('axial_ball','head_ball') else {'protraction_retraction':a,'elevation_depression':b,'upward_downward_rotation':c}
  upper_dofs[key]=values;check_dofs(row,bone['joint_class'],values,key)
 trunk=math.degrees((chest.tail-chest.head).angle(up))
 if trunk>10:fail(row,'trunk_tilt',trunk,10)
 hand_gap=measured_hand_mesh_projection(rig,hand_calibration)
 if hand_gap['projected_gap_armature_units']<0:fail(row,'projected_hand_mesh_gap',hand_gap['projected_gap_armature_units'],0)
 now={b['blender_name']:list(t.to_quaternion().normalized()) for b,t in zip(payload['bones'],transforms)}
 step=max((rotation_step_degrees(previous[n],v) for n,v in now.items()),default=0) if previous else 0
 if step>30:fail(row,'sampled_joint_continuity',step,30)
 previous=now
 records.append({'frame':row['frame'],'phase':phase,'elapsed':row['elapsed'],'contact_error':contact_error,'plant_drift':drift,'global_displacement_from_initial_stance':global_drift,'support_margin':balance['signed_balance_margin'],'balance':balance,'roles':roles,'wrist':wrist,'tracking_deg':tracking,'ankle':ankles,'elbow_deg':elbows,'trunk_deg':trunk,'joint_step_deg':step,'runtime_replay_error':roundtrip,'leg_foot_chain_length_error':chain_error,'lower_dofs':lower_dofs,'upper_dofs':upper_dofs,'hand_gap':hand_gap})
 if len(records)%60==0:print('BBM8_AUDIT',len(records),phase,'failures',len(failures),flush=True)
summary={p:{'samples':len(rs),'contact_max':max(r['contact_error'] for r in rs),'plant_drift_max':max(r['plant_drift'] for r in rs),'support_margin_min':min(r['support_margin'] for r in rs),'trunk_max':max(r['trunk_deg'] for r in rs),'tracking_max':max(max(r['tracking_deg'].values()) for r in rs),'joint_step_max':max(r['joint_step_deg'] for r in rs),'replay_error_max':max(r['runtime_replay_error'] for r in rs)} for p in ('ENTRY','ACTIVE','EXIT') if (rs:=[r for r in records if r['phase']==p])}
boundaries=[]
rows=observed['observations']
for before,after in zip(rows,rows[1:]):
 if before['phase']==after['phase'] or before['phase'] not in ('ENTRY','ACTIVE','EXIT'):continue
 distance=(Vector(before['bones'][0][4:])-Vector(after['bones'][0][4:])).length
 boundaries.append({'from':before['phase'],'to':after['phase'],'frame':after['frame'],'root_translation_delta':distance})
 if distance>limits['root_boundary']:fail(after,'root_phase_boundary',distance,limits['root_boundary'])
result={'status':'FAIL' if failures else 'RUNTIME_GEOMETRY_PASS_REQUIRES_VISUAL_AND_REGRESSION_REVIEW','method':'actual Godot observed transforms converted through source-bound bridge to original GLB, evaluated skin; no Blender render; GPU skinning visually inspected separately','limits':limits,'root_phase_boundaries':boundaries,'summary':summary,'failures':failures,'samples':records,'source_sha256':payload['source_glb_sha256'],'runtime_sha256':hashlib.sha256((OUT/'runtime.json').read_bytes()).hexdigest(),'full_preferred_joint_envelope':'Measured actual geometry: hip Rx/Rz/Ry, knee Rx/Ry, wrist Rx/Rz; shoulder flex/abduction from humerus direction relative to observed chest frame, axial roll from projected transported front with exact reconstruction; axial/clavicle local Rx/Rz/Ry engine convention. No tissue/artistic certification.'}
(OUT/'geometry_audit.json').write_text(json.dumps(result,separators=(',',':'))+'\n')
print('BBM8_GEOMETRY',result['status'],json.dumps(summary),len(failures),flush=True)

